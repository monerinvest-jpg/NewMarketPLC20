"""
VK Market → marketplace import.

The seller connects their VK account (OAuth, see vk_client), picks one of the
communities they administer, previews its market items and imports selected
(or all) of them into their shop:

  * idempotent upsert by (shop_id, source='vk', external_id=<vk item id>) —
    re-importing updates title/description/price instead of duplicating;
  * photos are DOWNLOADED and re-uploaded to our public bucket (VK CDN URLs
    expire), first photo becomes the main image;
  * availability: VK 0=available → in stock (default 1 unit unless it's a
    re-import), everything else → out of stock (quantity 0);
  * new products go through the usual premoderation setting.

The heavy work (photo downloads) runs in the Celery task import_vk_products.
"""
import asyncio
from decimal import Decimal
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Product, ProductImage, ProductStatus, Shop, ShopIntegration
from app.services import vk_client


def normalize_item(item: dict) -> dict:
    """VK market item → neutral dict for preview/import."""
    price = item.get("price") or {}
    amount = Decimal(str(price.get("amount", "0"))) / 100  # kopecks → rubles
    return {
        "external_id": str(item.get("id")),
        "title": (item.get("title") or "Без названия")[:512],
        "description": item.get("description") or "",
        "price": str(amount),
        "currency": (price.get("currency") or {}).get("name", "RUB"),
        "available": item.get("availability", 0) == 0,
        "sku": item.get("sku") or "",
        "photo": vk_client.best_photo_url(item),
        "photos": vk_client.all_photo_urls(item),
    }


async def get_integration(db: AsyncSession, shop_id: int) -> Optional[ShopIntegration]:
    return (await db.execute(
        select(ShopIntegration).where(
            ShopIntegration.shop_id == shop_id, ShopIntegration.provider == "vk"
        )
    )).scalar_one_or_none()


async def preview_items(token: str, community_id: int, limit: int = 200) -> list[dict]:
    items, total = await vk_client.get_market_page(token, community_id, offset=0, count=limit)
    return [normalize_item(i) for i in items]


async def _download(url: str) -> Optional[tuple[bytes, str]]:
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content, resp.headers.get("content-type", "image/jpeg")
    except Exception:
        return None


async def import_products(
    db: AsyncSession,
    shop: Shop,
    token: str,
    community_id: int,
    category_id: int,
    external_ids: Optional[list[str]] = None,
    progress_cb=None,
) -> dict:
    """
    Import (all or selected) market items of the community into the shop.
    Returns {"created": n, "updated": n, "skipped": n, "total": n}.
    """
    from app.services.settings_service import is_premoderation_enabled
    from app.services.slug_service import product_slug
    from app.services import storage_service

    premod = await is_premoderation_enabled(db)
    wanted = set(external_ids) if external_ids else None

    created = updated = skipped = done = 0
    offset, total = 0, 1
    while offset < total:
        items, total = await vk_client.get_market_page(token, community_id, offset=offset)
        if not items:
            break
        offset += len(items)

        for raw in items:
            norm = normalize_item(raw)
            if wanted is not None and norm["external_id"] not in wanted:
                continue
            done += 1

            existing = (await db.execute(
                select(Product).where(
                    Product.shop_id == shop.id,
                    Product.source == "vk",
                    Product.external_id == norm["external_id"],
                )
            )).scalar_one_or_none()

            if existing:
                existing.title = norm["title"]
                existing.description = norm["description"]
                existing.price = Decimal(norm["price"])
                if not norm["available"]:
                    existing.quantity = 0
                updated += 1
            else:
                product = Product(
                    shop_id=shop.id,
                    category_id=category_id,
                    title=norm["title"],
                    description=norm["description"],
                    price=Decimal(norm["price"]) if Decimal(norm["price"]) > 0 else Decimal("1.00"),
                    quantity=1 if norm["available"] else 0,
                    status=ProductStatus.pending if premod else ProductStatus.active,
                    source="vk",
                    external_id=norm["external_id"],
                )
                db.add(product)
                await db.flush()
                product.slug = product_slug(product.title, product.id)

                # Re-host photos in OUR bucket (VK CDN links expire).
                for i, url in enumerate(norm["photos"]):
                    downloaded = await _download(url)
                    if not downloaded:
                        continue
                    content, ctype = downloaded
                    try:
                        stored_url = await storage_service.save_file(
                            content, ctype, f"vk_{norm['external_id']}_{i}.jpg"
                        )
                    except Exception:
                        continue
                    db.add(ProductImage(
                        product_id=product.id, url=stored_url,
                        is_main=(i == 0), sort_order=i,
                    ))
                created += 1
                # Be polite to the VK CDN / our event loop on huge catalogs.
                await asyncio.sleep(0.1)

            if progress_cb:
                progress_cb(done, created, updated)

        await db.commit()

    return {"created": created, "updated": updated, "skipped": skipped, "total": done}

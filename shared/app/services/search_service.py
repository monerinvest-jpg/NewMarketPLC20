"""
Search service. Abstracts product search so it can use MeiliSearch when
configured, and transparently falls back to a database ILIKE search otherwise.
The fallback means search always works with zero extra infrastructure.

Indexing: `reindex_all_products()` pushes every active product into the Meili
`products` index (called by the nightly/hourly Celery task and after bulk
imports). Meili gives typo tolerance, RU morphology-agnostic prefix search and
relevance ranking that ILIKE cannot.
"""
from typing import Optional

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.models import Category, Product, ProductStatus, Shop

_INDEX = "products"


def _meili_configured() -> bool:
    return bool(getattr(settings, "MEILI_URL", "") and getattr(settings, "MEILI_KEY", ""))


def _meili_headers() -> dict:
    return {"Authorization": f"Bearer {settings.MEILI_KEY}"}


async def search_products(
    db: AsyncSession,
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """
    Search active products by query. Returns {"items": [...], "total": n,
    "engine": "meili"|"db"}. The ILIKE fallback ranks exact title prefix matches
    above substring matches.
    """
    if _meili_configured():
        try:
            return await _search_meili(db, query, limit, offset)
        except Exception:
            # Any MeiliSearch error: degrade gracefully to the DB search
            pass
    return await _search_db(db, query, limit, offset)


async def _search_db(db: AsyncSession, query: str, limit: int, offset: int) -> dict:
    pattern = f"%{query}%"
    base = select(Product).where(
        Product.status == ProductStatus.active,
        or_(
            Product.title.ilike(pattern),
            Product.description.ilike(pattern),
        ),
    )
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    # Order: title matches first (prefix, then any), then the rest
    prefix = f"{query}%"
    rows = (await db.execute(
        base.options(selectinload(Product.images))
        .order_by(
            Product.title.ilike(prefix).desc(),
            Product.rating.desc(),
        )
        .offset(offset).limit(limit)
    )).scalars().all()

    return {"items": rows, "total": total, "engine": "db"}


async def _search_meili(db: AsyncSession, query: str, limit: int, offset: int) -> dict:
    """
    Query the Meili index for ids, then hydrate full ORM products from the DB
    (so the response shape matches the catalog exactly), preserving Meili's
    relevance order. Raises on any failure so the caller can fall back.
    """
    import httpx

    url = settings.MEILI_URL.rstrip("/") + f"/indexes/{_INDEX}/search"
    async with httpx.AsyncClient(timeout=3.0) as client:
        resp = await client.post(
            url,
            json={"q": query, "limit": limit, "offset": offset, "attributesToRetrieve": ["id"]},
            headers=_meili_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    ids = [hit["id"] for hit in data.get("hits", [])]
    if not ids:
        return {"items": [], "total": 0, "engine": "meili"}

    rows = (await db.execute(
        select(Product)
        .where(Product.id.in_(ids), Product.status == ProductStatus.active)
        .options(selectinload(Product.images))
    )).scalars().all()
    by_id = {p.id: p for p in rows}
    items = [by_id[i] for i in ids if i in by_id]
    return {"items": items, "total": data.get("estimatedTotalHits", len(items)), "engine": "meili"}


async def suggest(db: AsyncSession, query: str, limit: int = 6) -> dict:
    """
    Lightweight header-autocomplete payload: a few matching products (with
    thumbnail + price), plus matching categories and shops. DB prefix/substring
    search — fast enough at suggest sizes with or without Meili.
    """
    pattern = f"%{query}%"
    prefix = f"{query}%"

    products = (await db.execute(
        select(Product)
        .where(Product.status == ProductStatus.active, Product.title.ilike(pattern))
        .options(selectinload(Product.images))
        .order_by(Product.title.ilike(prefix).desc(), Product.rating.desc())
        .limit(limit)
    )).scalars().all()

    categories = (await db.execute(
        select(Category).where(Category.name.ilike(pattern)).limit(3)
    )).scalars().all()

    shops = (await db.execute(
        select(Shop).where(Shop.name.ilike(pattern), Shop.is_active == True).limit(3)  # noqa: E712
    )).scalars().all()

    def _img(p: Product) -> Optional[str]:
        main = next((i for i in p.images if i.is_main), None) or (p.images[0] if p.images else None)
        return main.url if main else None

    return {
        "products": [
            {"id": p.id, "title": p.title, "price": str(p.price), "image_url": _img(p)}
            for p in products
        ],
        "categories": [{"id": c.id, "name": c.name} for c in categories],
        "shops": [{"id": s.id, "name": s.name} for s in shops],
    }


async def reindex_all_products() -> int:
    """
    Full rebuild of the Meili `products` index from the DB (idempotent; used by
    the scheduled Celery task). No-op returning -1 when Meili isn't configured.
    """
    if not _meili_configured():
        return -1
    import httpx

    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Product)
            .where(Product.status == ProductStatus.active)
            .options(selectinload(Product.images))
        )).scalars().all()
        docs = []
        for p in rows:
            main = next((i for i in p.images if i.is_main), None) or (p.images[0] if p.images else None)
            docs.append({
                "id": p.id,
                "title": p.title,
                "description": (p.description or "")[:2000],
                "price": float(p.price),
                "rating": float(p.rating or 0),
                "category_id": p.category_id,
                "shop_id": p.shop_id,
                "image_url": main.url if main else None,
            })

    base = settings.MEILI_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Ensure the index + sane settings exist (idempotent PATCH).
        await client.post(base + "/indexes", json={"uid": _INDEX, "primaryKey": "id"}, headers=_meili_headers())
        await client.patch(
            base + f"/indexes/{_INDEX}/settings",
            json={
                "searchableAttributes": ["title", "description"],
                "displayedAttributes": ["id", "title", "price", "image_url"],
                "rankingRules": ["words", "typo", "proximity", "attribute", "sort", "exactness"],
            },
            headers=_meili_headers(),
        )
        # Replace all documents (full rebuild keeps deletions in sync).
        resp = await client.put(base + f"/indexes/{_INDEX}/documents", json=docs, headers=_meili_headers())
        resp.raise_for_status()
    return len(docs)

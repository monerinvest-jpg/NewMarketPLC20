"""
Search service. Abstracts product search so it can use MeiliSearch when
configured, and transparently falls back to a database ILIKE search otherwise.
The fallback means search always works with zero extra infrastructure.
"""
from typing import Optional

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.models import Product, ProductStatus


def _meili_configured() -> bool:
    return bool(getattr(settings, "MEILI_URL", "") and getattr(settings, "MEILI_KEY", ""))


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
            return await _search_meili(query, limit, offset)
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


async def _search_meili(query: str, limit: int, offset: int) -> dict:
    """
    Query a MeiliSearch index. Imported lazily; raises on any failure so the
    caller can fall back. Returns product ids that the caller would hydrate —
    here we keep it simple and raise NotImplemented to force DB fallback unless
    a real client is wired up in deployment.
    """
    import httpx

    url = settings.MEILI_URL.rstrip("/") + "/indexes/products/search"
    headers = {"Authorization": f"Bearer {settings.MEILI_KEY}"}
    async with httpx.AsyncClient(timeout=3.0) as client:
        resp = await client.post(url, json={"q": query, "limit": limit, "offset": offset}, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    # MeiliSearch returns hydrated documents; we pass them through as-is.
    return {"items": data.get("hits", []), "total": data.get("estimatedTotalHits", 0), "engine": "meili"}

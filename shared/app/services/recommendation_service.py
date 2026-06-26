"""
Recommendation engine: "bought together", personalized, and cart-based.

The co-purchase signal is materialized into product_co_purchase by
`rebuild_co_purchase` (run periodically and on demand) so per-request reads are
a single indexed lookup. Reads gracefully fall back to same-category and
top-rated products when there isn't enough purchase history yet.

Only *real* purchases count toward co-purchase — orders that reached at least
the `paid` state. Pending, cancelled and refunded orders are ignored.
"""
from collections import defaultdict
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.models.models import (
    Order, OrderItem, OrderStatus, Product, ProductCoPurchase, ProductStatus,
)

# Order states that represent a completed sale (count toward co-purchase).
PURCHASED_STATUSES = (
    OrderStatus.paid, OrderStatus.processing, OrderStatus.shipped,
    OrderStatus.delivered, OrderStatus.completed,
)


async def rebuild_co_purchase(db: AsyncSession) -> int:
    """
    Recompute the materialized co-purchase table from scratch. For every pair of
    distinct products that appear together in a purchased order, store the number
    of such shared orders as the pair's score (directed both ways).

    Returns the number of directed pairs written. The caller commits.
    """
    oi1 = aliased(OrderItem)
    oi2 = aliased(OrderItem)
    rows = (await db.execute(
        select(
            oi1.product_id, oi2.product_id,
            func.count(func.distinct(oi1.order_id)).label("score"),
        )
        .select_from(oi1)
        .join(oi2, oi1.order_id == oi2.order_id)
        .join(Order, Order.id == oi1.order_id)
        .where(oi1.product_id != oi2.product_id, Order.status.in_(PURCHASED_STATUSES))
        .group_by(oi1.product_id, oi2.product_id)
    )).all()

    await db.execute(delete(ProductCoPurchase))
    for product_id, related_id, score in rows:
        db.add(ProductCoPurchase(
            product_id=product_id, related_product_id=related_id, score=int(score),
        ))
    await db.flush()
    return len(rows)


async def _load_products_in_order(db: AsyncSession, ids: list[int]) -> list[Product]:
    """Load active products by id, preserving the order of `ids`."""
    if not ids:
        return []
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id.in_(ids), Product.status == ProductStatus.active)
    )
    by_id = {p.id: p for p in result.scalars().all()}
    return [by_id[i] for i in ids if i in by_id]


async def _category_fallback(
    db: AsyncSession, product_id: int, exclude: set[int], limit: int
) -> list[int]:
    prod = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not prod:
        return []
    rows = (await db.execute(
        select(Product.id)
        .where(
            Product.category_id == prod.category_id,
            Product.id != product_id,
            Product.status == ProductStatus.active,
        )
        .order_by(Product.rating.desc())
        .limit(limit * 2)
    )).all()
    return [r[0] for r in rows if r[0] not in exclude][:limit]


async def get_product_recommendations(
    db: AsyncSession, product_id: int, limit: int = 8
) -> list[Product]:
    """"Bought together" for a product, with same-category fallback."""
    co = (await db.execute(
        select(ProductCoPurchase.related_product_id)
        .where(ProductCoPurchase.product_id == product_id)
        .order_by(ProductCoPurchase.score.desc())
        .limit(limit)
    )).all()
    ids = [r[0] for r in co]

    if len(ids) < limit:
        exclude = set(ids) | {product_id}
        ids += await _category_fallback(db, product_id, exclude, limit - len(ids))

    return await _load_products_in_order(db, ids[:limit])


async def _user_purchased_product_ids(db: AsyncSession, user_id: int) -> list[int]:
    rows = (await db.execute(
        select(OrderItem.product_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.buyer_id == user_id, Order.status.in_(PURCHASED_STATUSES))
        .distinct()
    )).all()
    return [r[0] for r in rows]


async def recommended_for_user(
    db: AsyncSession, user_id: int, limit: int = 12
) -> list[Product]:
    """
    Personalized recommendations: aggregate co-purchase scores across everything
    the user has bought, excluding products they already own. Falls back to
    top-rated active products for new users with no history.
    """
    purchased = await _user_purchased_product_ids(db, user_id)
    purchased_set = set(purchased)

    ranked: list[int] = []
    if purchased:
        rows = (await db.execute(
            select(
                ProductCoPurchase.related_product_id,
                func.sum(ProductCoPurchase.score).label("score"),
            )
            .where(ProductCoPurchase.product_id.in_(purchased))
            .group_by(ProductCoPurchase.related_product_id)
            .order_by(func.sum(ProductCoPurchase.score).desc())
            .limit(limit * 3)
        )).all()
        ranked = [r[0] for r in rows if r[0] not in purchased_set]

    if len(ranked) < limit:
        # Fallback: popular, well-rated active products the user doesn't own.
        exclude = purchased_set | set(ranked)
        rows = (await db.execute(
            select(Product.id)
            .where(Product.status == ProductStatus.active)
            .order_by(Product.rating.desc(), Product.reviews_count.desc())
            .limit(limit * 3)
        )).all()
        for (pid,) in rows:
            if pid not in exclude:
                ranked.append(pid)
            if len(ranked) >= limit:
                break

    return await _load_products_in_order(db, ranked[:limit])


async def cart_recommendations(
    db: AsyncSession, product_ids: list[int], limit: int = 8
) -> list[Product]:
    """"Frequently bought with your cart": aggregate co-purchase across the cart,
    excluding what's already in it."""
    if not product_ids:
        return []
    in_cart = set(product_ids)
    rows = (await db.execute(
        select(
            ProductCoPurchase.related_product_id,
            func.sum(ProductCoPurchase.score).label("score"),
        )
        .where(ProductCoPurchase.product_id.in_(product_ids))
        .group_by(ProductCoPurchase.related_product_id)
        .order_by(func.sum(ProductCoPurchase.score).desc())
        .limit(limit * 3)
    )).all()
    ranked = [r[0] for r in rows if r[0] not in in_cart][:limit]
    return await _load_products_in_order(db, ranked)

"""
Rating aggregation for products and sellers (shops).

Ratings are derived only from *approved* reviews. A product's rating averages
the reviews on that product; a shop's (seller's) rating averages the reviews
across all of its products. Both values are denormalized onto the respective
rows (Product.rating/reviews_count, Shop.rating/reviews_count) so listings and
cards don't pay an aggregation cost on every read.

Call `recalculate_for_product` after any change to a product's reviews — it
refreshes both the product and its owning shop. The caller is responsible for
committing the surrounding transaction.
"""
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Product, Review, ReviewStatus, Shop


async def recalculate_product_rating(db: AsyncSession, product_id: int) -> None:
    avg_rating, count = (await db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.product_id == product_id,
            Review.status == ReviewStatus.approved,
        )
    )).one()
    await db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(rating=round(avg_rating, 2) if avg_rating else 0, reviews_count=count)
    )


async def recalculate_shop_rating(db: AsyncSession, shop_id: int) -> None:
    """Average of approved reviews across all products of the shop."""
    avg_rating, count = (await db.execute(
        select(func.avg(Review.rating), func.count(Review.id))
        .select_from(Review)
        .join(Product, Review.product_id == Product.id)
        .where(Product.shop_id == shop_id, Review.status == ReviewStatus.approved)
    )).one()
    await db.execute(
        update(Shop)
        .where(Shop.id == shop_id)
        .values(rating=round(avg_rating, 2) if avg_rating else Decimal("0.00"),
                reviews_count=count or 0)
    )


async def recalculate_for_product(db: AsyncSession, product_id: int) -> None:
    """Refresh both the product rating and its owning shop's rating."""
    await recalculate_product_rating(db, product_id)
    shop_id = (await db.execute(
        select(Product.shop_id).where(Product.id == product_id)
    )).scalar_one_or_none()
    if shop_id is not None:
        await recalculate_shop_rating(db, shop_id)


async def shop_rating_summary(db: AsyncSession, shop_id: int) -> dict:
    """
    Rating overview for a seller: average, total approved reviews, the count of
    verified-purchase reviews, and the 1–5 star distribution.
    """
    rows = (await db.execute(
        select(Review.rating, func.count(Review.id))
        .join(Product, Review.product_id == Product.id)
        .where(Product.shop_id == shop_id, Review.status == ReviewStatus.approved)
        .group_by(Review.rating)
    )).all()
    distribution = {str(star): 0 for star in range(1, 6)}
    total = 0
    weighted = 0
    for star, cnt in rows:
        distribution[str(int(star))] = cnt
        total += cnt
        weighted += int(star) * cnt

    verified = (await db.execute(
        select(func.count(Review.id))
        .join(Product, Review.product_id == Product.id)
        .where(
            Product.shop_id == shop_id,
            Review.status == ReviewStatus.approved,
            Review.is_verified_purchase.is_(True),
        )
    )).scalar_one()

    avg = round(weighted / total, 2) if total else 0.0
    return {
        "shop_id": shop_id,
        "rating": avg,
        "reviews_count": total,
        "verified_count": verified or 0,
        "distribution": distribution,
    }

"""
Shop following: buyers subscribe to shops to get a personal feed of new
products / flash sales and notifications when a followed shop posts something.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    NotificationType, Notification, Product, ProductStatus, Shop, ShopFollow,
)


async def is_following(db: AsyncSession, user_id: int, shop_id: int) -> bool:
    return (await db.execute(
        select(ShopFollow.id).where(ShopFollow.user_id == user_id, ShopFollow.shop_id == shop_id)
    )).scalar_one_or_none() is not None


async def follower_count(db: AsyncSession, shop_id: int) -> int:
    return (await db.execute(
        select(func.count()).select_from(ShopFollow).where(ShopFollow.shop_id == shop_id)
    )).scalar_one()


async def follow(db: AsyncSession, user_id: int, shop_id: int) -> bool:
    if await is_following(db, user_id, shop_id):
        return False
    db.add(ShopFollow(user_id=user_id, shop_id=shop_id))
    await db.flush()
    return True


async def unfollow(db: AsyncSession, user_id: int, shop_id: int) -> bool:
    row = (await db.execute(
        select(ShopFollow).where(ShopFollow.user_id == user_id, ShopFollow.shop_id == shop_id)
    )).scalar_one_or_none()
    if not row:
        return False
    await db.delete(row)
    await db.flush()
    return True


async def followed_shop_ids(db: AsyncSession, user_id: int) -> list[int]:
    rows = (await db.execute(
        select(ShopFollow.shop_id).where(ShopFollow.user_id == user_id)
    )).all()
    return [r[0] for r in rows]


async def followed_shops(db: AsyncSession, user_id: int) -> list[Shop]:
    ids = await followed_shop_ids(db, user_id)
    if not ids:
        return []
    rows = (await db.execute(select(Shop).where(Shop.id.in_(ids)))).scalars().all()
    return list(rows)


async def feed(db: AsyncSession, user_id: int, limit: int = 24) -> list[Product]:
    """Recent active products from the shops the user follows."""
    ids = await followed_shop_ids(db, user_id)
    if not ids:
        return []
    rows = (await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.shop_id.in_(ids), Product.status == ProductStatus.active)
        .order_by(Product.created_at.desc())
        .limit(limit)
    )).scalars().all()
    return list(rows)


async def notify_followers(
    db: AsyncSession, shop_id: int, title: str, body: str, link: str
) -> int:
    """Fan-out a notification to every follower of a shop. Returns the count."""
    follower_ids = (await db.execute(
        select(ShopFollow.user_id).where(ShopFollow.shop_id == shop_id)
    )).all()
    n = 0
    for (uid,) in follower_ids:
        db.add(Notification(
            user_id=uid, type=NotificationType.shop_update, title=title, body=body, link=link,
        ))
        n += 1
    return n

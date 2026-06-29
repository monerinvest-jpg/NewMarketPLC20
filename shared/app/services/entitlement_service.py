"""
Entitlements: a buyer's right to access a digital product/course after payment.

Granted when an order's payment succeeds (idempotent — safe to call on every
webhook re-delivery), checked on every download, revoked on refund/cancel.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Entitlement, Order, ProductType


def _is_digital(item) -> bool:
    return bool(item.product) and item.product.product_type in (ProductType.digital, ProductType.course)


def order_has_physical(order: Order) -> bool:
    """True if any item still needs physical fulfillment (shipping)."""
    return any(
        item.product and item.product.product_type == ProductType.physical
        for item in order.items
    )


def order_is_digital_only(order: Order) -> bool:
    return bool(order.items) and not order_has_physical(order)


async def grant_for_order(db: AsyncSession, order: Order) -> int:
    """
    Create an Entitlement for each digital/course item in `order`. Idempotent:
    skips items that already have a grant for this (user, product, order), so a
    re-delivered payment webhook never double-grants. `order.items` must be loaded
    with their `.product`. Returns how many new grants were created. Caller commits.
    """
    granted = 0
    for item in order.items:
        if not _is_digital(item):
            continue
        exists = (await db.execute(
            select(Entitlement.id).where(
                Entitlement.user_id == order.buyer_id,
                Entitlement.product_id == item.product_id,
                Entitlement.order_id == order.id,
            )
        )).scalar_one_or_none()
        if exists:
            continue
        db.add(Entitlement(
            user_id=order.buyer_id,
            product_id=item.product_id,
            order_id=order.id,
            order_item_id=item.id,
        ))
        granted += 1
    await db.flush()
    return granted


async def revoke_for_order(db: AsyncSession, order: Order) -> None:
    """Revoke all entitlements granted by an order (on refund/cancel). Caller commits."""
    rows = (await db.execute(
        select(Entitlement).where(Entitlement.order_id == order.id)
    )).scalars().all()
    for e in rows:
        e.revoked = True


async def get_active_entitlement(db: AsyncSession, user_id: int, product_id: int) -> Optional[Entitlement]:
    """The buyer's (non-revoked) entitlement to a product, if any."""
    return (await db.execute(
        select(Entitlement).where(
            Entitlement.user_id == user_id,
            Entitlement.product_id == product_id,
            Entitlement.revoked == False,  # noqa: E712
        ).limit(1)
    )).scalar_one_or_none()

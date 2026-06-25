"""
Seller payout service.

A single buyer order can contain products from multiple shops. Each shop's
payout must be calculated and credited independently using that item's own
commission rate (OrderItem.platform_fee / seller_net), never assumed to be
the whole order's seller_net. This module is the single place that performs
payouts so order completion (manual, admin, and the Celery auto-complete
task) all share the same correct logic.
"""
from collections import defaultdict
from decimal import Decimal
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    Order, OrderItem, Shop, Transaction, TransactionType, User,
)


async def payout_sellers_for_order(order: Order, db: AsyncSession) -> Dict[int, Decimal]:
    """
    Credits every distinct seller in `order` their own seller_net, summed
    across only the items belonging to that seller's shop. Idempotent: items
    already marked payout_status='paid' are skipped, so calling this twice
    (e.g. once from a manual status change and once from the Celery beat
    auto-complete task) never double-pays a seller.

    Returns a dict of {shop_id: amount_paid} for logging/testing purposes.
    """
    items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id, OrderItem.payout_status == "pending")
    )
    pending_items = items_result.scalars().all()
    if not pending_items:
        return {}

    # Group pending items by shop so each seller is credited once per order
    by_shop: Dict[int, list] = defaultdict(list)
    for item in pending_items:
        by_shop[item.shop_id].append(item)

    paid: Dict[int, Decimal] = {}

    for shop_id, items in by_shop.items():
        shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
        shop = shop_result.scalar_one_or_none()
        if not shop:
            continue

        owner_result = await db.execute(select(User).where(User.id == shop.owner_id))
        owner = owner_result.scalar_one_or_none()
        if not owner:
            continue

        shop_seller_net = sum((item.seller_net for item in items), Decimal("0.00"))
        if shop_seller_net <= 0:
            for item in items:
                item.payout_status = "paid"
            continue

        owner.balance += shop_seller_net
        tx = Transaction(
            user_id=owner.id,
            type=TransactionType.order_payment,
            amount=shop_seller_net,
            order_id=order.id,
            description=f"Выплата за заказ #{order.id} (магазин «{shop.name}»)",
            balance_after=owner.balance,
        )
        db.add(tx)
        shop.total_sales += 1

        for item in items:
            item.payout_status = "paid"

        paid[shop_id] = shop_seller_net

    await db.flush()
    return paid


async def refund_sellers_for_order(order: Order, db: AsyncSession) -> None:
    """
    Marks all of an order's items as refunded (no payout owed). Used when an
    order is cancelled/refunded before any seller payout occurred. Items
    already paid are left untouched — reversing a completed payout is a
    separate manual/admin operation, not handled here.
    """
    items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id, OrderItem.payout_status == "pending")
    )
    for item in items_result.scalars().all():
        item.payout_status = "refunded"
    await db.flush()


async def get_distinct_shop_ids_for_order(order_id: int, db: AsyncSession) -> list[int]:
    """Returns every distinct shop_id represented in an order's items."""
    result = await db.execute(
        select(OrderItem.shop_id).where(OrderItem.order_id == order_id).distinct()
    )
    return [row[0] for row in result.all()]

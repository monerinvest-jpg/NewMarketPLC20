"""
Sub-order service. A multi-shop order is split into one SubOrder per shop so
each seller manages their own fulfillment (status + tracking) independently.
The order's overall status is *derived* from its sub-orders.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Order, OrderItem, OrderStatus, SubOrder, SubOrderStatus,
)


async def create_sub_orders_for_order(order: Order, db: AsyncSession) -> None:
    """
    Create one SubOrder per distinct shop in the order and link each OrderItem
    to its shop's SubOrder. Called right after order items are created.
    """
    items = (await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )).scalars().all()

    sub_by_shop: dict[int, SubOrder] = {}
    for item in items:
        if item.shop_id not in sub_by_shop:
            so = SubOrder(order_id=order.id, shop_id=item.shop_id, status=SubOrderStatus.processing)
            db.add(so)
            await db.flush()
            sub_by_shop[item.shop_id] = so
        item.sub_order_id = sub_by_shop[item.shop_id].id
    await db.flush()


# Maps the "lowest common" fulfillment state across sub-orders to an order status.
# The overall order is only as advanced as its least-advanced sub-order.
_RANK = {
    SubOrderStatus.processing: 0,
    SubOrderStatus.shipped: 1,
    SubOrderStatus.delivered: 2,
    SubOrderStatus.completed: 3,
    SubOrderStatus.cancelled: 3,
}

_TO_ORDER_STATUS = {
    SubOrderStatus.processing: OrderStatus.processing,
    SubOrderStatus.shipped: OrderStatus.shipped,
    SubOrderStatus.delivered: OrderStatus.delivered,
    SubOrderStatus.completed: OrderStatus.completed,
}


async def recompute_order_status(order: Order, db: AsyncSession) -> None:
    """
    Derive the order's overall status from its sub-orders. The order advances to
    'shipped'/'delivered'/'completed' only when ALL non-cancelled sub-orders have
    reached at least that stage. If every sub-order is cancelled, so is the order.
    Orders still awaiting payment are left untouched.
    """
    if order.status in (OrderStatus.pending_payment, OrderStatus.cancelled, OrderStatus.refunded):
        return

    subs = (await db.execute(
        select(SubOrder).where(SubOrder.order_id == order.id)
    )).scalars().all()
    if not subs:
        return

    active = [s for s in subs if s.status != SubOrderStatus.cancelled]
    if not active:
        order.status = OrderStatus.cancelled
        return

    # Overall = the least-advanced active sub-order
    least = min(active, key=lambda s: _RANK[s.status])
    new_status = _TO_ORDER_STATUS.get(least.status)
    if new_status:
        order.status = new_status

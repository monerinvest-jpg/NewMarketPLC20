"""
Loyalty / cashback service. When an order completes, the buyer earns bonus
points (added to their bonus_balance) equal to a configurable percentage of
the order subtotal. These points can then be spent on future orders via the
existing bonus system.
"""
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    BalanceTransaction, BalanceTransactionType, NotificationType, Order, User,
)
from app.services.notification_service import notify
from app.services.settings_service import get_setting


async def award_cashback_for_order(order: Order, db: AsyncSession) -> Decimal:
    """
    Credit cashback points to the buyer for a completed order. Idempotent via
    a marker BalanceTransaction (reference_type='cashback', reference_id=order.id):
    if one already exists for this order, no points are awarded again.
    Returns the amount awarded (0 if disabled or already awarded).
    """
    enabled = (await get_setting(db, "enable_loyalty_cashback")).lower() == "true"
    if not enabled:
        return Decimal("0")

    # Idempotency guard
    existing = await db.execute(
        select(BalanceTransaction).where(
            BalanceTransaction.reference_type == "cashback",
            BalanceTransaction.reference_id == order.id,
        )
    )
    if existing.scalar_one_or_none():
        return Decimal("0")

    # Accumulate qualifying spend and refresh the buyer's loyalty tier, then use
    # the tier's cashback rate (falling back to the flat setting).
    from app.services import loyalty_tier_service
    await loyalty_tier_service.ensure_default_tiers(db)
    tier = await loyalty_tier_service.on_order_completed(db, order)

    flat_percent = Decimal(await get_setting(db, "loyalty_cashback_percent"))
    percent = tier.cashback_percent if tier else flat_percent
    cashback = (order.subtotal * percent / Decimal("100")).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    if cashback <= 0:
        return Decimal("0")

    buyer = (await db.execute(select(User).where(User.id == order.buyer_id))).scalar_one_or_none()
    if not buyer:
        return Decimal("0")

    buyer.bonus_balance += cashback
    db.add(BalanceTransaction(
        user_id=buyer.id,
        change=cashback,
        type=BalanceTransactionType.credit,
        reference_type="cashback",
        reference_id=order.id,
        description=f"Кэшбэк баллами за заказ #{order.id}",
        balance_after=buyer.bonus_balance,
    ))
    await notify(
        db, buyer.id, NotificationType.system,
        title=f"Начислен кэшбэк: {cashback} баллов",
        body=f"За заказ #{order.id}",
        link="/profile",
    )
    return cashback

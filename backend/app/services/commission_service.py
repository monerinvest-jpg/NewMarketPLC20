"""
Commission calculation service.
Determines the effective commission rate for an order and
computes platform_fee / seller_net.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import SellerPlan, SellerSubscription, Shop, SubscriptionStatus
from app.services.settings_service import get_global_commission


async def get_effective_commission(db: AsyncSession, shop: Shop) -> Decimal:
    """
    Resolve the commission % to apply to a shop, in priority order:

    1. Admin-set per-shop override (shop.commission_percent) — always wins if set.
       This lets an admin pin a special rate for a specific shop regardless of plan.
    2. The commission of the shop's active subscription plan — the paid/free tier
       trade-off (paid plan = lower commission, free plan = higher commission).
    3. The global default commission from settings.
    """
    if shop.commission_percent is not None:
        return shop.commission_percent

    # Look up an active (or trial) subscription and use its plan's commission
    sub_result = await db.execute(
        select(SellerSubscription).where(SellerSubscription.shop_id == shop.id)
    )
    subscription = sub_result.scalar_one_or_none()
    if subscription and subscription.status in (SubscriptionStatus.active, SubscriptionStatus.trial):
        # Treat an expired period as no longer entitled to the plan's rate
        not_expired = (
            subscription.current_period_end is None
            or subscription.current_period_end > datetime.now(timezone.utc)
        )
        if not_expired:
            plan_result = await db.execute(
                select(SellerPlan).where(SellerPlan.id == subscription.plan_id)
            )
            plan = plan_result.scalar_one_or_none()
            if plan:
                return plan.commission_percent

    return await get_global_commission(db)


def calculate_order_financials(
    subtotal: Decimal,
    delivery_cost: Decimal,
    commission_percent: Decimal,
    bonus_used: Decimal = Decimal("0"),
    coupon_discount: Decimal = Decimal("0"),
) -> dict:
    """
    Calculate all financial fields for an order.

    Returns:
        platform_fee      – amount the platform keeps from the subtotal
        seller_net        – amount credited to the seller
        total_price       – amount the buyer pays (subtotal + delivery - bonus - coupon)
        commission_percent_used – the commission rate applied
    """
    platform_fee = (subtotal * commission_percent / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    seller_net = (subtotal - platform_fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Discount applied before charging buyer; does not reduce platform fee
    discount = (bonus_used + coupon_discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_price = max(
        (subtotal + delivery_cost - discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        Decimal("1.00"),  # minimum 1 ruble to avoid zero-value payments
    )

    return {
        "platform_fee": platform_fee,
        "seller_net": seller_net,
        "total_price": total_price,
        "commission_percent_used": commission_percent,
    }


def calculate_item_financials(line_subtotal: Decimal, commission_percent: Decimal) -> dict:
    """
    Calculate the platform fee and seller payout for a single order item's
    line subtotal (price_at_time * quantity), using that item's own shop
    commission rate. This is the authoritative per-seller calculation used
    when an order spans multiple shops — each shop's payout is computed
    independently from its own items, never assumed to be the whole order.

    Returns:
        platform_fee – platform's cut of this line item
        seller_net   – amount owed to this item's seller
    """
    platform_fee = (line_subtotal * commission_percent / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    seller_net = (line_subtotal - platform_fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"platform_fee": platform_fee, "seller_net": seller_net}

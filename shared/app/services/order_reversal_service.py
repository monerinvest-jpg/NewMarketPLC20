"""
Order reversal: the single place that undoes a cancelled/refunded order's
side effects. Both the manual cancel path (update_order_status) and the
gateway-driven YooKassa webhook call this so the two never diverge.

What it restores, exactly once per order:
  * stock — each item's quantity is returned to the product/variant + a
    StockMovement is logged;
  * unpaid payouts — items still `pending` are marked `refunded` so no seller
    is ever paid out for a cancelled order;
  * buyer bonus points spent on the order (`bonus_used`);
  * buyer promo balance spent on the order (`promo_used`);
  * the coupon's `used_count` (so a cancelled order frees up the usage slot).

Idempotency is the CALLER's responsibility: guard the call by order/payment
status (e.g. only reverse when the order is not already cancelled). Calling it
twice would double-restore stock and balances.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    BalanceTransaction, BalanceTransactionType, Coupon, Order,
    ProductType, PromoBalanceTransaction, User,
)


async def restore_order(db: AsyncSession, order: Order) -> None:
    """Undo a cancelled order's stock and buyer-side credits. Caller commits."""
    from app.services.stock_service import record_movement
    from app.services.payout_service import refund_sellers_for_order
    from app.services import entitlement_service

    # 1. Return stock for every PHYSICAL item (digital/course have no stock).
    # record_movement re-loads the row and applies the increment.
    for item in order.items:
        if item.product is not None and item.product.product_type != ProductType.physical:
            continue
        await record_movement(
            db, item.product_id, item.quantity, "cancel",
            variant_id=item.variant_id, note="Отмена заказа", apply_to_stock=True,
        )

    # 1b. Revoke any digital/course access granted by this order.
    await entitlement_service.revoke_for_order(db, order)

    # 2. Never pay out a cancelled order: mark still-pending items refunded.
    await refund_sellers_for_order(order, db)

    # 3. Refund buyer bonus + promo balance. Both live on the buyer User row.
    buyer = (await db.execute(
        select(User).where(User.id == order.buyer_id)
    )).scalar_one_or_none()

    if buyer:
        if order.bonus_used and order.bonus_used > 0:
            buyer.bonus_balance += order.bonus_used
            db.add(BalanceTransaction(
                user_id=buyer.id,
                change=order.bonus_used,
                type=BalanceTransactionType.credit,
                reference_type="order_cancel",
                reference_id=order.id,
                description=f"Возврат бонусов по отменённому заказу #{order.id}",
                balance_after=buyer.bonus_balance,
            ))

        if order.promo_used and order.promo_used > 0:
            buyer.promo_balance = (buyer.promo_balance or Decimal("0.00")) + order.promo_used
            db.add(PromoBalanceTransaction(
                user_id=buyer.id,
                change=order.promo_used,
                kind="order_refund",
                description=f"Возврат промо-баланса по заказу #{order.id}",
                balance_after=buyer.promo_balance,
            ))

        if getattr(order, "referral_used", None) and order.referral_used > 0:
            buyer.referral_balance = (buyer.referral_balance or Decimal("0.00")) + order.referral_used
            db.add(BalanceTransaction(
                user_id=buyer.id,
                change=order.referral_used,
                type=BalanceTransactionType.credit,
                reference_type="order_cancel",
                reference_id=order.id,
                description=f"Возврат реферального баланса по заказу #{order.id}",
                balance_after=buyer.referral_balance,
            ))

    # 4. Free up the coupon usage slot.
    if order.coupon_id:
        coupon = (await db.execute(
            select(Coupon).where(Coupon.id == order.coupon_id)
        )).scalar_one_or_none()
        if coupon and coupon.used_count > 0:
            coupon.used_count -= 1

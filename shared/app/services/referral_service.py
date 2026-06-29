"""
Referral programme logic.
"""
import secrets
import string
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    BalanceTransaction, BalanceTransactionType, Order, OrderStatus,
    Referral, ReferralReward, ReferralType, Transaction, TransactionType, User, UserRole,
)
from app.services.settings_service import get_referral_settings


def generate_referral_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def ensure_referral_code(user: User, db: AsyncSession) -> str:
    """Assign a unique referral code to a user if they don't have one."""
    if user.referral_code:
        return user.referral_code
    while True:
        code = generate_referral_code()
        result = await db.execute(select(User).where(User.referral_code == code))
        if not result.scalar_one_or_none():
            user.referral_code = code
            await db.flush()
            return code


async def register_referral(referred_user: User, referral_code: str, db: AsyncSession) -> Optional[Referral]:
    """
    Called at registration if a referral code was provided.
    Links the new user to the referrer.
    """
    result = await db.execute(select(User).where(User.referral_code == referral_code))
    referrer = result.scalar_one_or_none()
    if not referrer or referrer.id == referred_user.id:
        return None

    ref_type = ReferralType.seller if referred_user.role == UserRole.seller else ReferralType.buyer

    referral = Referral(
        referrer_id=referrer.id,
        referred_user_id=referred_user.id,
        type=ref_type,
        code=referral_code,
        reward_paid=False,
    )
    db.add(referral)
    await db.flush()
    return referral


async def _already_rewarded(db: AsyncSession, referral_id: int, order_id: int) -> bool:
    """True if this referral already earned a reward for this order (idempotency)."""
    rid = (await db.execute(
        select(ReferralReward.id).where(
            ReferralReward.referral_id == referral_id,
            ReferralReward.order_id == order_id,
        )
    )).scalar_one_or_none()
    return rid is not None


async def process_buyer_referral_reward(order: Order, db: AsyncSession) -> None:
    """
    LIFELONG referral: pays the referrer a percentage of EVERY completed order of
    a referred buyer (not just the first). The earning goes to the referrer's
    withdrawable referral_balance. Idempotent per (referral, order).
    """
    referral = (await db.execute(
        select(Referral).where(
            Referral.referred_user_id == order.buyer_id,
            Referral.type == ReferralType.buyer,
        )
    )).scalar_one_or_none()
    if not referral:
        return
    if await _already_rewarded(db, referral.id, order.id):
        return

    settings = await get_referral_settings(db)
    if order.subtotal < settings["referral_buyer_min_order_amount"]:
        return
    percent = settings["referral_buyer_bonus_percent"]
    bonus = (order.subtotal * percent / Decimal("100")).quantize(Decimal("0.01"))
    if bonus <= 0:
        return

    referrer = (await db.execute(select(User).where(User.id == referral.referrer_id))).scalar_one_or_none()
    if not referrer:
        return

    referrer.referral_balance += bonus
    db.add(ReferralReward(
        referral_id=referral.id, order_id=order.id, amount=bonus,
        type=ReferralType.buyer, status="paid",
    ))
    db.add(BalanceTransaction(
        user_id=referrer.id, change=bonus, type=BalanceTransactionType.credit,
        reference_type="referral", reference_id=order.id,
        description=f"Реферальный доход с покупки приглашённого (заказ #{order.id})",
        balance_after=referrer.referral_balance,
    ))
    referral.reward_paid = True
    await db.flush()


async def process_seller_referral_reward(order: Order, db: AsyncSession) -> None:
    """
    LIFELONG referral: pays the referrer a percentage of EVERY completed sale of a
    referred seller (not just their first), for each referred shop in the order.
    The % is taken of that shop's own items subtotal and credited to the
    referrer's withdrawable referral_balance. Idempotent per (referral, order).
    """
    from app.models.models import Shop, OrderItem

    shop_ids = [row[0] for row in (await db.execute(
        select(OrderItem.shop_id).where(OrderItem.order_id == order.id).distinct()
    )).all()]
    if not shop_ids:
        return

    settings = await get_referral_settings(db)
    percent = settings["referral_seller_bonus_percent"]

    for shop_id in shop_ids:
        shop = (await db.execute(select(Shop).where(Shop.id == shop_id))).scalar_one_or_none()
        if not shop:
            continue
        referral = (await db.execute(
            select(Referral).where(
                Referral.referred_user_id == shop.owner_id,
                Referral.type == ReferralType.seller,
            )
        )).scalar_one_or_none()
        if not referral or await _already_rewarded(db, referral.id, order.id):
            continue

        # Percentage of THIS shop's items in the order (the referred seller's sale).
        shop_subtotal = (await db.execute(
            select(func.coalesce(func.sum(OrderItem.price_at_time * OrderItem.quantity), 0))
            .where(OrderItem.order_id == order.id, OrderItem.shop_id == shop_id)
        )).scalar_one()
        reward_amount = (Decimal(str(shop_subtotal)) * percent / Decimal("100")).quantize(Decimal("0.01"))
        if reward_amount <= 0:
            continue

        referrer = (await db.execute(select(User).where(User.id == referral.referrer_id))).scalar_one_or_none()
        if not referrer:
            continue

        referrer.referral_balance += reward_amount
        db.add(ReferralReward(
            referral_id=referral.id, order_id=order.id, amount=reward_amount,
            type=ReferralType.seller, status="paid",
        ))
        db.add(Transaction(
            user_id=referrer.id, type=TransactionType.referral_reward, amount=reward_amount,
            order_id=order.id, description="Реферальный доход с продажи приглашённого продавца",
            balance_after=referrer.referral_balance,
        ))
        db.add(BalanceTransaction(
            user_id=referrer.id, change=reward_amount, type=BalanceTransactionType.credit,
            reference_type="referral", reference_id=order.id,
            description=f"Реферальный доход с продавца (заказ #{order.id})",
            balance_after=referrer.referral_balance,
        ))
        referral.reward_paid = True
        await db.flush()
    await db.flush()

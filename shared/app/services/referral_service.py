"""
Referral programme logic.
"""
import secrets
import string
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
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


async def process_buyer_referral_reward(order: Order, db: AsyncSession) -> None:
    """
    Called when a buyer completes their first qualifying order.
    Pays the referrer their buyer bonus.
    """
    result = await db.execute(
        select(Referral).where(
            Referral.referred_user_id == order.buyer_id,
            Referral.type == ReferralType.buyer,
            Referral.reward_paid == False,  # noqa: E712
        )
    )
    referral = result.scalar_one_or_none()
    if not referral:
        return

    settings = await get_referral_settings(db)
    min_amount = settings["referral_buyer_min_order_amount"]

    if order.subtotal < min_amount:
        return

    # Bonus is a percentage of the referred buyer's first qualifying order
    # subtotal, credited to the referrer as bonus points. The % is admin-tunable.
    percent = settings["referral_buyer_bonus_percent"]
    bonus = (order.subtotal * percent / Decimal("100")).quantize(Decimal("0.01"))
    if bonus <= 0:
        return

    # Credit bonus points to referrer
    referrer_result = await db.execute(select(User).where(User.id == referral.referrer_id))
    referrer = referrer_result.scalar_one_or_none()
    if not referrer:
        return

    referrer.bonus_balance += bonus

    reward = ReferralReward(
        referral_id=referral.id,
        amount=bonus,
        type=ReferralType.buyer,
        status="paid",
    )
    db.add(reward)

    bal_tx = BalanceTransaction(
        user_id=referrer.id,
        change=bonus,
        type=BalanceTransactionType.credit,
        reference_type="referral",
        reference_id=referral.id,
        description=f"Реферальный бонус за привлечение покупателя (заказ #{order.id})",
        balance_after=referrer.bonus_balance,
    )
    db.add(bal_tx)

    referral.reward_paid = True
    await db.flush()


async def process_seller_referral_reward(order: Order, db: AsyncSession) -> None:
    """
    Called when the first completed order of a referred seller reaches 'completed'.
    Pays the referrer the seller cash bonus, for every distinct seller present
    in the order (an order can contain items from multiple shops — each one
    is checked independently rather than assuming a single seller).
    """
    from app.models.models import Shop, OrderItem

    shop_ids_result = await db.execute(
        select(OrderItem.shop_id).where(OrderItem.order_id == order.id).distinct()
    )
    shop_ids = [row[0] for row in shop_ids_result.all()]
    if not shop_ids:
        return

    for shop_id in shop_ids:
        shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
        shop = shop_result.scalar_one_or_none()
        if not shop:
            continue

        result = await db.execute(
            select(Referral).where(
                Referral.referred_user_id == shop.owner_id,
                Referral.type == ReferralType.seller,
                Referral.reward_paid == False,  # noqa: E712
            )
        )
        referral = result.scalar_one_or_none()
        if not referral:
            continue

        settings = await get_referral_settings(db)
        # Reward is a percentage of the referred seller's first completed order
        # subtotal, paid to the referrer's balance. The % is admin-tunable.
        percent = settings["referral_seller_bonus_percent"]
        reward_amount = (order.subtotal * percent / Decimal("100")).quantize(Decimal("0.01"))
        if reward_amount <= 0:
            continue

        referrer_result = await db.execute(select(User).where(User.id == referral.referrer_id))
        referrer = referrer_result.scalar_one_or_none()
        if not referrer:
            continue

        referrer.balance += reward_amount

        reward = ReferralReward(
            referral_id=referral.id,
            amount=reward_amount,
            type=ReferralType.seller,
            status="paid",
        )
        db.add(reward)

        tx = Transaction(
            user_id=referrer.id,
            type=TransactionType.referral_reward,
            amount=reward_amount,
            order_id=order.id,
            description="Реферальное вознаграждение за привлечение продавца",
            balance_after=referrer.balance,
        )
        db.add(tx)

        bal_tx = BalanceTransaction(
            user_id=referrer.id,
            change=reward_amount,
            type=BalanceTransactionType.credit,
            reference_type="referral",
            reference_id=referral.id,
            description=f"Реферальное вознаграждение за продавца (заказ #{order.id})",
            balance_after=referrer.balance,
        )
        db.add(bal_tx)

        referral.reward_paid = True
        await db.flush()
    await db.flush()

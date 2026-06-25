"""
Seller subscription service.

Handles a seller choosing a tariff plan and paying for it. Payment can come
either from the seller's own balance (their accrued earnings) or via an
external YooKassa payment — both are supported. Free plans and trial periods
are activated immediately without payment.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    BalanceTransaction, BalanceTransactionType, SellerPlan, SellerSubscription,
    SubscriptionStatus, Transaction, TransactionType, User, Shop,
)
from app.services.settings_service import get_setting


async def is_paid_placement_enabled(db: AsyncSession) -> bool:
    """Whether the platform offers paid seller placement at all (admin toggle)."""
    val = await get_setting(db, "enable_paid_placement")
    return val.lower() == "true"


async def get_default_plan(db: AsyncSession) -> Optional[SellerPlan]:
    result = await db.execute(
        select(SellerPlan).where(SellerPlan.is_default == True, SellerPlan.is_active == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def get_or_create_subscription(shop: Shop, db: AsyncSession) -> Optional[SellerSubscription]:
    """
    Returns the shop's subscription, creating a default-plan one if missing and
    a default plan exists. Returns None if no default plan is configured.
    """
    result = await db.execute(
        select(SellerSubscription).where(SellerSubscription.shop_id == shop.id)
    )
    subscription = result.scalar_one_or_none()
    if subscription:
        return subscription

    default_plan = await get_default_plan(db)
    if not default_plan:
        return None

    subscription = SellerSubscription(
        shop_id=shop.id,
        plan_id=default_plan.id,
        status=SubscriptionStatus.active,
        current_period_end=None,  # default/free plan never expires
    )
    db.add(subscription)
    await db.flush()
    return subscription


async def subscribe_to_plan(
    shop: Shop,
    plan_id: int,
    db: AsyncSession,
    pay_from_balance: bool = True,
) -> dict:
    """
    Switch a shop to `plan_id`.

    - Free plan (monthly_price == 0): activated immediately.
    - Paid plan with an unused trial: starts a trial period, no charge yet.
    - Paid plan, no trial / trial used:
        * pay_from_balance=True  → charge the seller's balance now.
        * pay_from_balance=False → caller should create a YooKassa payment and
          call activate_paid_subscription once it succeeds; here we just record
          the chosen plan in a 'pending' state by returning needs_payment.

    Returns a dict describing what happened / what the caller must do next.
    """
    plan_result = await db.execute(
        select(SellerPlan).where(SellerPlan.id == plan_id, SellerPlan.is_active == True)  # noqa: E712
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="План не найден или неактивен")

    sub_result = await db.execute(
        select(SellerSubscription).where(SellerSubscription.shop_id == shop.id)
    )
    subscription = sub_result.scalar_one_or_none()
    if not subscription:
        subscription = SellerSubscription(shop_id=shop.id, plan_id=plan.id)
        db.add(subscription)
        await db.flush()

    now = datetime.now(timezone.utc)

    # Free plan
    if plan.monthly_price <= 0:
        subscription.plan_id = plan.id
        subscription.status = SubscriptionStatus.active
        subscription.current_period_end = None
        await db.flush()
        return {"status": "active", "plan": plan.name, "charged": "0.00"}

    # Paid plan with an available trial
    if plan.trial_days > 0 and not subscription.trial_used:
        subscription.plan_id = plan.id
        subscription.status = SubscriptionStatus.trial
        subscription.trial_used = True
        subscription.current_period_end = now + timedelta(days=plan.trial_days)
        await db.flush()
        return {
            "status": "trial",
            "plan": plan.name,
            "charged": "0.00",
            "trial_until": subscription.current_period_end.isoformat(),
        }

    # Paid plan, charge required
    if pay_from_balance:
        owner_result = await db.execute(select(User).where(User.id == shop.owner_id))
        owner = owner_result.scalar_one_or_none()
        if not owner:
            raise HTTPException(status_code=404, detail="Владелец магазина не найден")
        if owner.balance < plan.monthly_price:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно средств на балансе ({owner.balance} ₽). "
                       f"Стоимость плана: {plan.monthly_price} ₽",
            )
        owner.balance -= plan.monthly_price
        tx = Transaction(
            user_id=owner.id,
            type=TransactionType.payout,
            amount=-plan.monthly_price,
            description=f"Оплата подписки «{plan.name}» (1 месяц)",
            balance_after=owner.balance,
        )
        db.add(tx)
        bal_tx = BalanceTransaction(
            user_id=owner.id,
            change=-plan.monthly_price,
            type=BalanceTransactionType.debit,
            reference_type="subscription",
            reference_id=subscription.id,
            description=f"Оплата подписки «{plan.name}»",
            balance_after=owner.balance,
        )
        db.add(bal_tx)

        _activate_period(subscription, plan, now)
        await db.flush()
        return {"status": "active", "plan": plan.name, "charged": str(plan.monthly_price)}

    # Defer to external payment
    return {
        "status": "needs_payment",
        "plan_id": plan.id,
        "plan": plan.name,
        "amount": str(plan.monthly_price),
    }


async def activate_paid_subscription(shop: Shop, plan_id: int, db: AsyncSession) -> None:
    """Called after a successful external (YooKassa) subscription payment."""
    plan_result = await db.execute(select(SellerPlan).where(SellerPlan.id == plan_id))
    plan = plan_result.scalar_one_or_none()
    if not plan:
        return
    sub_result = await db.execute(
        select(SellerSubscription).where(SellerSubscription.shop_id == shop.id)
    )
    subscription = sub_result.scalar_one_or_none()
    if not subscription:
        subscription = SellerSubscription(shop_id=shop.id, plan_id=plan.id)
        db.add(subscription)
        await db.flush()
    _activate_period(subscription, plan, datetime.now(timezone.utc))
    await db.flush()


def _activate_period(subscription: SellerSubscription, plan: SellerPlan, now: datetime) -> None:
    subscription.plan_id = plan.id
    subscription.status = SubscriptionStatus.active
    # Extend from the later of "now" or the existing period end (stacking renewals)
    base = subscription.current_period_end if (
        subscription.current_period_end and subscription.current_period_end > now
    ) else now
    subscription.current_period_end = base + timedelta(days=30)

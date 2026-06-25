"""
Seller subscription endpoints: view plans, current subscription, subscribe.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_seller
from app.core.database import get_db
from app.models.models import SellerPlan, Shop, User
from app.schemas.schemas import (
    SellerPlanOut, SellerSubscriptionOut, SubscribeRequest,
)
from app.services.subscription_service import (
    get_or_create_subscription, is_paid_placement_enabled, subscribe_to_plan,
)

router = APIRouter(prefix="/subscription", tags=["subscription"])


async def _get_my_shop(user: User, db: AsyncSession) -> Shop:
    result = await db.execute(select(Shop).where(Shop.owner_id == user.id))
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="У вас ещё нет магазина")
    return shop


@router.get("/plans", response_model=list[SellerPlanOut])
async def list_plans(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_seller)):
    """Active plans available to sellers, sorted for display."""
    result = await db.execute(
        select(SellerPlan).where(SellerPlan.is_active == True)  # noqa: E712
        .order_by(SellerPlan.sort_order, SellerPlan.monthly_price)
    )
    return result.scalars().all()


@router.get("/me", response_model=Optional[SellerSubscriptionOut])
async def my_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    from sqlalchemy.orm import selectinload
    from app.models.models import SellerSubscription

    shop = await _get_my_shop(current_user, db)
    sub = await get_or_create_subscription(shop, db)
    await db.commit()
    if not sub:
        return None
    result = await db.execute(
        select(SellerSubscription)
        .options(selectinload(SellerSubscription.plan))
        .where(SellerSubscription.id == sub.id)
    )
    return result.scalar_one()


@router.get("/status")
async def paid_placement_status(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_seller)):
    """Tells the frontend whether paid placement / plan selection is enabled at all."""
    enabled = await is_paid_placement_enabled(db)
    return {"paid_placement_enabled": enabled}


@router.post("/subscribe")
async def subscribe(
    payload: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """
    Subscribe the seller's shop to a plan. Free plans and trials activate
    immediately. Paid plans either charge the balance (pay_from_balance=True)
    or return a YooKassa confirmation_url to redirect to (pay_from_balance=False).
    """
    if not await is_paid_placement_enabled(db):
        raise HTTPException(status_code=400, detail="Платное размещение сейчас отключено")

    shop = await _get_my_shop(current_user, db)
    result = await subscribe_to_plan(shop, payload.plan_id, db, pay_from_balance=payload.pay_from_balance)

    # If external payment is required, create a YooKassa payment for the plan.
    # Subscription payments aren't tied to an Order (Payment.order_id is an
    # order FK), so we don't persist a Payment row here — we just return the
    # confirmation URL for the seller to complete payment, then activation
    # happens via the subscription webhook / confirmation callback.
    if result.get("status") == "needs_payment":
        from app.services.payment_service import get_payment_gateway
        from decimal import Decimal
        try:
            gw = get_payment_gateway()
            pay_result = await gw.create_payment(
                order_id=shop.id,  # reference tag only
                amount=Decimal(result["amount"]),
                description=f"Подписка «{result['plan']}» для магазина {shop.name} (plan:{payload.plan_id})",
                return_url=None,
            )
            await db.commit()
            return {
                "status": "needs_payment",
                "plan": result["plan"],
                "plan_id": payload.plan_id,
                "amount": result["amount"],
                "confirmation_url": pay_result.confirmation_url,
            }
        except Exception:
            await db.rollback()
            raise HTTPException(status_code=502, detail="Не удалось создать платёж за подписку")

    await db.commit()
    return result

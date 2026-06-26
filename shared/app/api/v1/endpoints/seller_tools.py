"""
Block 3 endpoints: seller-created coupons and payout (withdrawal) requests.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_seller, get_current_user
from app.core.database import get_db
from app.models.models import (
    BalanceTransaction, BalanceTransactionType, NotificationType,
    PayoutRequest, PayoutRequestStatus, SellerCoupon, Shop, Transaction,
    TransactionType, User,
)
from app.schemas.schemas import (
    PayoutRequestCreate, PayoutRequestOut, SellerCouponCreate, SellerCouponOut,
)
from app.services.notification_service import notify

router = APIRouter(prefix="/seller", tags=["seller-tools"])


async def _get_my_shop(user: User, db: AsyncSession) -> Shop:
    result = await db.execute(select(Shop).where(Shop.owner_id == user.id))
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="У вас ещё нет магазина")
    return shop


# ─── Seller coupons ──────────────────────────────────────────────────────────────

@router.get("/coupons", response_model=list[SellerCouponOut])
async def list_seller_coupons(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_my_shop(current_user, db)
    result = await db.execute(
        select(SellerCoupon).where(SellerCoupon.shop_id == shop.id).order_by(SellerCoupon.created_at.desc())
    )
    return result.scalars().all()


@router.post("/coupons", response_model=SellerCouponOut, status_code=201)
async def create_seller_coupon(
    payload: SellerCouponCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_my_shop(current_user, db)
    # Ensure code is globally unique (shared code space with admin coupons table is separate,
    # but seller_coupon.code itself is unique)
    existing = await db.execute(select(SellerCoupon).where(SellerCoupon.code == payload.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Промокод с таким кодом уже существует")
    coupon = SellerCoupon(shop_id=shop.id, **payload.model_dump())
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    return coupon


@router.delete("/coupons/{coupon_id}", status_code=204)
async def delete_seller_coupon(
    coupon_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_my_shop(current_user, db)
    result = await db.execute(
        select(SellerCoupon).where(SellerCoupon.id == coupon_id, SellerCoupon.shop_id == shop.id)
    )
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="Промокод не найден")
    await db.delete(coupon)
    await db.commit()


# ─── Payout requests ─────────────────────────────────────────────────────────────

@router.get("/payouts", response_model=list[PayoutRequestOut])
async def my_payout_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    result = await db.execute(
        select(PayoutRequest).where(PayoutRequest.user_id == current_user.id)
        .order_by(PayoutRequest.created_at.desc())
    )
    return result.scalars().all()


@router.post("/payouts", response_model=PayoutRequestOut, status_code=201)
async def request_payout(
    payload: PayoutRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """
    Seller requests a withdrawal. The amount is validated against their current
    balance but NOT deducted yet — deduction happens when an admin marks the
    request 'paid', so a rejected request never touches the balance.
    """
    if payload.amount > current_user.balance:
        raise HTTPException(
            status_code=400,
            detail=f"Сумма превышает доступный баланс ({current_user.balance} ₽)",
        )
    # Prevent stacking requests that together exceed the balance
    pending = await db.execute(
        select(PayoutRequest).where(
            PayoutRequest.user_id == current_user.id,
            PayoutRequest.status.in_([PayoutRequestStatus.pending, PayoutRequestStatus.approved]),
        )
    )
    reserved = sum((p.amount for p in pending.scalars().all()), Decimal("0"))
    if reserved + payload.amount > current_user.balance:
        raise HTTPException(
            status_code=400,
            detail="С учётом уже запрошенных выводов сумма превышает баланс",
        )

    req = PayoutRequest(
        user_id=current_user.id,
        amount=payload.amount,
        payout_details=payload.payout_details,
        status=PayoutRequestStatus.pending,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req

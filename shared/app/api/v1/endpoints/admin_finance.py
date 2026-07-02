"""
Admin API — Money: coupons, referral bonuses, seller plans, payout requests, currencies.

Split out of the former monolithic admin.py; mounted via the admin hub
(app.api.v1.endpoints.admin), same /admin prefix and RBAC dependencies.
"""
"""
Admin API endpoints. All require moderator or superadmin role.
"""
from decimal import Decimal
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_moderator_or_admin, get_current_superadmin, get_current_seller
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.models import (
    BalanceTransaction, BalanceTransactionType, Coupon, FiscalReceipt, FiscalReceiptStatus,
    FiscalReceiptType, Order, OrderItem, OrderStatus,
    Payment, PaymentStatus, Product, ProductStatus, Referral, Report, ReportStatus,
    Review, ReviewStatus, Shop, Transaction, TransactionType, User, UserRole, Category, Setting,
)
from app.schemas.schemas import (
    BulkSettingsUpdate, CouponCreate, CouponOut, DashboardStats,
    FiscalReceiptOut,
    OrderOut, OrderStatusUpdate, ProductModerationUpdate, ProductOut,
    ReportOut, ReportUpdate, SettingOut, SettingUpdate,
    ShopAdminUpdate, ShopOut, UserAdminUpdate, UserOut, CategoryCreate, CategoryOut, CategoryUpdate,
    ReviewOut, ReviewModerationUpdate,
    FeatureFlagOut, FeatureFlagUpsert, UserPermissionsUpdate, AdminBalanceAdjust,
)
from app.services import fiscal_service
from app.services.settings_service import get_all_settings, set_setting

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/coupons", response_model=list[CouponOut])
async def list_coupons(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    result = await db.execute(select(Coupon).order_by(Coupon.created_at.desc()))
    return result.scalars().all()


@router.post("/coupons", response_model=CouponOut, status_code=201)
async def create_coupon(
    payload: CouponCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    from sqlalchemy.exc import IntegrityError
    coupon = Coupon(**payload.model_dump())
    db.add(coupon)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Coupon code already exists")
    await db.refresh(coupon)
    return coupon


@router.delete("/coupons/{coupon_id}", status_code=204)
async def delete_coupon(
    coupon_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    await db.delete(coupon)
    await db.commit()


# ─── Moderators management (superadmin only) ──────────────────────────────────

@router.get("/referrals", response_model=dict)
async def list_referrals(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(Referral)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    result = await db.execute(query.order_by(Referral.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    referrals = result.scalars().all()
    from app.schemas.schemas import ReferralOut
    return {"items": [ReferralOut.model_validate(r) for r in referrals], "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.post("/referrals/manual-bonus")
async def manual_bonus(
    user_id: int,
    amount: Decimal,
    is_cash: bool = False,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """Manually credit bonus or cash to a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if is_cash:
        user.balance += amount
    else:
        user.bonus_balance += amount

    bal_tx = BalanceTransaction(
        user_id=user.id,
        change=amount,
        type=BalanceTransactionType.credit,
        reference_type="manual",
        description="Ручное начисление администратором",
        balance_after=user.balance if is_cash else user.bonus_balance,
    )
    db.add(bal_tx)
    await db.commit()
    return {"status": "credited", "amount": amount}


# ─── Seller plans (paid placement / tariffs) ───────────────────────────────────

@router.get("/plans", response_model=list)
async def list_plans_admin(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.models.models import SellerPlan
    from app.schemas.schemas import SellerPlanOut
    result = await db.execute(select(SellerPlan).order_by(SellerPlan.sort_order, SellerPlan.monthly_price))
    return [SellerPlanOut.model_validate(p) for p in result.scalars().all()]


@router.post("/plans", status_code=201)
async def create_plan(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    from app.models.models import SellerPlan
    from app.schemas.schemas import SellerPlanCreate, SellerPlanOut
    data = SellerPlanCreate(**payload)
    # If this plan is marked default, unset any existing default
    if data.is_default:
        existing = await db.execute(select(SellerPlan).where(SellerPlan.is_default == True))  # noqa: E712
        for p in existing.scalars().all():
            p.is_default = False
    plan = SellerPlan(**data.model_dump())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return SellerPlanOut.model_validate(plan)


@router.put("/plans/{plan_id}")
async def update_plan(
    plan_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    from app.models.models import SellerPlan
    from app.schemas.schemas import SellerPlanUpdate, SellerPlanOut
    result = await db.execute(select(SellerPlan).where(SellerPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="План не найден")
    data = SellerPlanUpdate(**payload)
    if data.is_default:
        existing = await db.execute(select(SellerPlan).where(SellerPlan.is_default == True, SellerPlan.id != plan_id))  # noqa: E712
        for p in existing.scalars().all():
            p.is_default = False
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.commit()
    await db.refresh(plan)
    return SellerPlanOut.model_validate(plan)


@router.delete("/plans/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    from app.models.models import SellerPlan, SellerSubscription
    # Block deletion if any shop is currently on this plan
    in_use = await db.execute(select(SellerSubscription).where(SellerSubscription.plan_id == plan_id).limit(1))
    if in_use.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Нельзя удалить план: на нём есть активные подписки")
    result = await db.execute(select(SellerPlan).where(SellerPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="План не найден")
    await db.delete(plan)
    await db.commit()


# ─── Payout requests (admin processing) ────────────────────────────────────────

@router.get("/payouts", response_model=list)
async def list_payout_requests(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    from app.models.models import PayoutRequest
    query = select(PayoutRequest, User).join(User, User.id == PayoutRequest.user_id).order_by(PayoutRequest.created_at.desc())
    if status_filter:
        query = query.where(PayoutRequest.status == status_filter)
    rows = (await db.execute(query)).all()
    return [
        {
            "id": p.id, "user_id": p.user_id, "amount": p.amount,
            "source": p.source.value if hasattr(p.source, "value") else p.source,
            "status": p.status.value if hasattr(p.status, "value") else p.status,
            "payout_details": p.payout_details, "admin_comment": p.admin_comment,
            "created_at": p.created_at.isoformat(),
            "processed_at": p.processed_at.isoformat() if p.processed_at else None,
            "user_email": u.email, "user_name": u.full_name,
            "user_email_verified": u.email_verified,
        }
        for p, u in rows
    ]


@router.post("/payouts/{payout_id}/process")
async def process_payout(
    payout_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator_or_admin),
):
    from datetime import datetime, timezone
    from app.models.models import (
        PayoutRequest, PayoutRequestStatus, BalanceTransaction,
        BalanceTransactionType, Transaction, TransactionType, NotificationType,
    )
    from app.schemas.schemas import PayoutProcessRequest, PayoutRequestOut
    from app.services.notification_service import notify

    data = PayoutProcessRequest(**payload)
    result = await db.execute(select(PayoutRequest).where(PayoutRequest.id == payout_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    if req.status in (PayoutRequestStatus.paid, PayoutRequestStatus.rejected):
        raise HTTPException(status_code=400, detail="Запрос уже обработан")

    new_status = PayoutRequestStatus(data.status)
    req.status = new_status
    req.admin_comment = data.admin_comment
    req.processed_by_id = current_user.id
    req.processed_at = datetime.now(timezone.utc)

    # On 'paid', deduct the amount from the matching balance (sales vs referral).
    if new_status == PayoutRequestStatus.paid:
        from app.models.models import PayoutSource
        user = (await db.execute(select(User).where(User.id == req.user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        is_referral = req.source == PayoutSource.referral
        available = user.referral_balance if is_referral else user.balance
        if available < req.amount:
            raise HTTPException(status_code=400, detail="Недостаточно средств на балансе пользователя")
        if is_referral:
            user.referral_balance -= req.amount
            balance_after = user.referral_balance
        else:
            user.balance -= req.amount
            balance_after = user.balance
        label = "Вывод реферальных средств" if is_referral else "Вывод средств"
        db.add(Transaction(
            user_id=user.id, type=TransactionType.payout, amount=-req.amount,
            description=f"{label} #{req.id}", balance_after=balance_after,
        ))
        db.add(BalanceTransaction(
            user_id=user.id, change=-req.amount, type=BalanceTransactionType.debit,
            reference_type="payout", reference_id=req.id,
            description=f"{label} #{req.id}", balance_after=balance_after,
        ))

    from app.services.audit_service import log_action
    await log_action(
        db, current_user.id, f"payout.{data.status}", "payout", req.id,
        detail=f"{req.amount} ₽; {data.admin_comment or ''}",
    )
    await notify(
        db, req.user_id, NotificationType.payout,
        title=f"Запрос на вывод: {data.status}",
        body=data.admin_comment or f"Сумма {req.amount} ₽",
        link="/seller/payouts",
    )
    await db.commit()
    await db.refresh(req)
    return PayoutRequestOut.model_validate(req)


# ─── Homepage banners ──────────────────────────────────────────────────────────

@router.get("/currencies")
async def admin_list_currencies(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.services.currency_service import get_rates
    rates = await get_rates(db)
    return [{"code": c, "rate": str(i["rate"]), "symbol": i["symbol"]} for c, i in rates.items()]


@router.put("/currencies")
async def admin_upsert_currency(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    from app.models.models import CurrencyRate, CurrencyCode
    from app.schemas.schemas import CurrencyRateUpsert
    data = CurrencyRateUpsert(**payload)
    existing = (await db.execute(
        select(CurrencyRate).where(CurrencyRate.code == CurrencyCode(data.code))
    )).scalar_one_or_none()
    if existing:
        existing.rate = data.rate
        existing.symbol = data.symbol
    else:
        db.add(CurrencyRate(code=CurrencyCode(data.code), rate=data.rate, symbol=data.symbol))
    await db.commit()
    return {"status": "ok"}


# ─── Return requests (admin oversight) ───────────────────────────────────────────

"""
Admin API — Users: list/update/balance/detail, moderators, granular permissions, my-menu.

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


@router.get("/users", response_model=dict)
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    query = select(User)
    if q:
        query = query.where(
            User.email.ilike(f"%{q}%") | User.full_name.ilike(f"%{q}%")
        )
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    result = await db.execute(query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    users = result.scalars().all()
    return {"items": [UserOut.model_validate(u) for u in users], "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator_or_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_superadmin = current_user.role == UserRole.superadmin or current_user.is_superuser
    data = payload.model_dump(exclude_unset=True)

    # Role and superuser elevation are superadmin-only.
    if ("role" in data or "is_superuser" in data) and not is_superadmin:
        raise HTTPException(status_code=403, detail="Менять роль и права суперпользователя может только суперадмин")

    # Email change must stay unique.
    new_email = data.pop("email", None)
    if new_email and new_email != user.email:
        exists = (await db.execute(select(User.id).where(User.email == new_email, User.id != user_id))).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=400, detail="Этот email уже используется")
        user.email = new_email

    new_password = data.pop("new_password", None)
    if new_password:
        from app.core.security import get_password_hash
        user.password_hash = get_password_hash(new_password)

    for field, value in data.items():
        setattr(user, field, value)

    from app.services.audit_service import log_action
    changed = ", ".join(sorted(set(list(data.keys()) + (["email"] if new_email else []) + (["password"] if new_password else []))))
    await log_action(db, current_user.id, "user.update", "user", user_id, detail=changed)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users/{user_id}/adjust-balance", response_model=UserOut)
async def adjust_user_balance(
    user_id: int,
    payload: AdminBalanceAdjust,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Manually credit/debit any of a user's balances, with an audit trail and a
    ledger entry. Superadmin only — this is a sensitive, money-moving action."""
    from app.models.models import BalanceTransaction, BalanceTransactionType
    from app.services.audit_service import log_action

    allowed = {"balance", "bonus_balance", "referral_balance", "promo_balance"}
    if payload.field not in allowed:
        raise HTTPException(status_code=400, detail=f"Недопустимый баланс. Разрешено: {', '.join(sorted(allowed))}")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    current = getattr(user, payload.field) or Decimal("0")
    new_value = (current + payload.amount).quantize(Decimal("0.01"))
    if new_value < 0:
        raise HTTPException(status_code=400, detail="Итоговый баланс не может быть отрицательным")
    setattr(user, payload.field, new_value)

    db.add(BalanceTransaction(
        user_id=user.id, change=payload.amount,
        type=BalanceTransactionType.credit if payload.amount >= 0 else BalanceTransactionType.debit,
        reference_type="admin_adjust", reference_id=current_user.id,
        description=f"[{payload.field}] {payload.reason}",
        balance_after=new_value,
    ))
    await log_action(
        db, current_user.id, "user.balance_adjust", "user", user_id,
        detail=f"{payload.field} {payload.amount:+} → {new_value}; {payload.reason}",
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/users/{user_id}")
async def user_detail(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """
    Full 360° view of a user for moderation / payout fraud review: profile,
    every balance, withdrawal requisites, lifetime stats, recent orders, payouts,
    balance ledger, referrals they made, recent staff actions, and risk flags.
    """
    from datetime import datetime, timedelta, timezone
    from app.models.models import (
        Order, PayoutRequest, Referral, ReferralReward, BalanceTransaction,
        AuditLog, WithdrawalAccount, Shop,
    )

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    def _sum(v) -> Decimal:
        return Decimal(str(v or 0))

    # Orders placed as a buyer
    orders_count = (await db.execute(
        select(func.count(Order.id)).where(Order.buyer_id == user_id)
    )).scalar_one()
    orders_total = _sum((await db.execute(
        select(func.sum(Order.total_price)).where(
            Order.buyer_id == user_id,
            Order.status.notin_(["pending_payment", "cancelled", "refunded"]),
        )
    )).scalar_one())
    recent_orders = (await db.execute(
        select(Order).where(Order.buyer_id == user_id).order_by(Order.created_at.desc()).limit(10)
    )).scalars().all()

    # Payouts (both sales and referral)
    payouts = (await db.execute(
        select(PayoutRequest).where(PayoutRequest.user_id == user_id)
        .order_by(PayoutRequest.created_at.desc()).limit(20)
    )).scalars().all()
    payouts_paid = _sum((await db.execute(
        select(func.sum(PayoutRequest.amount)).where(
            PayoutRequest.user_id == user_id, PayoutRequest.status == "paid")
    )).scalar_one())
    payouts_pending = _sum((await db.execute(
        select(func.sum(PayoutRequest.amount)).where(
            PayoutRequest.user_id == user_id, PayoutRequest.status.in_(["pending", "approved"]))
    )).scalar_one())
    ref_payouts_total = _sum((await db.execute(
        select(func.sum(PayoutRequest.amount)).where(
            PayoutRequest.user_id == user_id, PayoutRequest.source == "referral",
            PayoutRequest.status.in_(["pending", "approved", "paid"]))
    )).scalar_one())

    # Referrals this user made + lifetime referral earnings
    referrals_made = (await db.execute(
        select(func.count(Referral.id)).where(Referral.referrer_id == user_id)
    )).scalar_one()
    referrals_recent_7d = (await db.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == user_id,
            Referral.created_at >= datetime.now(timezone.utc) - timedelta(days=7),
        )
    )).scalar_one()
    referral_earned = _sum((await db.execute(
        select(func.sum(ReferralReward.amount)).select_from(ReferralReward)
        .join(Referral, Referral.id == ReferralReward.referral_id)
        .where(Referral.referrer_id == user_id)
    )).scalar_one())

    txns = (await db.execute(
        select(BalanceTransaction).where(BalanceTransaction.user_id == user_id)
        .order_by(BalanceTransaction.created_at.desc()).limit(20)
    )).scalars().all()
    actions = (await db.execute(
        select(AuditLog).where(AuditLog.actor_id == user_id)
        .order_by(AuditLog.created_at.desc()).limit(20)
    )).scalars().all()

    withdrawal_acc = (await db.execute(
        select(WithdrawalAccount).where(WithdrawalAccount.user_id == user_id)
    )).scalar_one_or_none()
    shop = (await db.execute(select(Shop).where(Shop.owner_id == user_id))).scalar_one_or_none()

    # ── Risk flags ────────────────────────────────────────────────────────────
    created = user.created_at
    now = datetime.now(timezone.utc)
    age_days = (now - created).days if created else 999
    has_pending = payouts_pending > 0
    flags: list[str] = []
    if has_pending and not user.email_verified:
        flags.append("Заявка на вывод при неподтверждённом email")
    if has_pending and age_days < 14:
        flags.append(f"Молодой аккаунт ({age_days} дн.) с заявкой на вывод")
    if ref_payouts_total > referral_earned:
        flags.append("Сумма реферальных выводов превышает начисленный реферальный доход")
    if referrals_recent_7d >= 20:
        flags.append(f"Высокая скорость приглашений: {referrals_recent_7d} за 7 дней")
    if has_pending and withdrawal_acc is None:
        flags.append("Заявка на вывод без сохранённых реквизитов")

    return {
        "user": UserOut.model_validate(user),
        "shop_id": shop.id if shop else None,
        "withdrawal_account": None if not withdrawal_acc else {
            "tax_regime": withdrawal_acc.tax_regime.value,
            "legal_name": withdrawal_acc.legal_name,
            "inn": withdrawal_acc.inn,
            "account_details": withdrawal_acc.account_details,
        },
        "stats": {
            "account_age_days": age_days,
            "orders_count": orders_count,
            "orders_total_spent": orders_total,
            "referrals_made": referrals_made,
            "referral_earned_total": referral_earned,
            "payouts_paid_total": payouts_paid,
            "payouts_pending_total": payouts_pending,
        },
        "risk_flags": flags,
        "recent_orders": [
            {"id": o.id, "total_price": o.total_price, "status": str(o.status.value if hasattr(o.status, "value") else o.status),
             "created_at": o.created_at.isoformat()} for o in recent_orders
        ],
        "payouts": [
            {"id": p.id, "amount": p.amount,
             "source": str(p.source.value if hasattr(p.source, "value") else p.source),
             "status": str(p.status.value if hasattr(p.status, "value") else p.status),
             "created_at": p.created_at.isoformat()} for p in payouts
        ],
        "balance_transactions": [
            {"change": t.change, "type": str(t.type.value if hasattr(t.type, "value") else t.type),
             "reference_type": t.reference_type, "description": t.description,
             "created_at": t.created_at.isoformat()} for t in txns
        ],
        "recent_actions": [
            {"action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
             "detail": a.detail, "created_at": a.created_at.isoformat()} for a in actions
        ],
    }


# ─── Shops ────────────────────────────────────────────────────────────────────

@router.get("/moderators", response_model=list[UserOut])
async def list_moderators(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    result = await db.execute(
        select(User).where(User.role == UserRole.moderator)
    )
    return result.scalars().all()


@router.post("/moderators/{user_id}/assign", response_model=UserOut)
async def assign_moderator(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = UserRole.moderator
    user.is_staff = True
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/moderators/{user_id}/remove", response_model=UserOut)
async def remove_moderator(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = UserRole.buyer
    user.is_staff = False
    await db.commit()
    await db.refresh(user)
    return user


# ─── Referrals ────────────────────────────────────────────────────────────────

@router.get("/permissions/catalog")
async def permissions_catalog(_: User = Depends(get_current_superadmin)):
    """The grantable permissions, grouped to mirror the admin sidebar, each with
    the menu items it unlocks (so the editor can show what a grant 'lights up')."""
    from app.services.rbac_service import ALL_PERMISSIONS, PERMISSION_GROUPS, menu_for_permission
    groups = []
    for g in PERMISSION_GROUPS:
        groups.append({
            "group": g["group"],
            "permissions": [
                {"key": k, "description": ALL_PERMISSIONS[k], "menu": menu_for_permission(k)}
                for k in g["keys"] if k in ALL_PERMISSIONS
            ],
        })
    return {"groups": groups}


@router.get("/my-menu")
async def my_menu(current_user: User = Depends(get_current_moderator_or_admin)):
    """Admin sidebar paths the CURRENT staff user may see (drives menu filtering)."""
    from app.services.rbac_service import allowed_menu_paths, get_permissions
    return {
        "paths": allowed_menu_paths(current_user),
        "permissions": get_permissions(current_user),
        "is_superadmin": current_user.role.value == "superadmin" or current_user.is_superuser,
    }


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    from app.services.rbac_service import get_permissions
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"user_id": user_id, "permissions": get_permissions(user)}


@router.put("/users/{user_id}/permissions")
async def set_user_permissions(
    user_id: int,
    payload: UserPermissionsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    from app.services.rbac_service import serialize_permissions
    from app.services.audit_service import log_action
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.permissions = serialize_permissions(payload.permissions)
    await log_action(
        db, current_user.id, "user.permissions", "user", user_id,
        detail=", ".join(payload.permissions),
    )
    await db.commit()
    return {"user_id": user_id, "permissions": payload.permissions}


# ─── Block D: SMS (SMSC.ru) management section ────────────────────────────────────

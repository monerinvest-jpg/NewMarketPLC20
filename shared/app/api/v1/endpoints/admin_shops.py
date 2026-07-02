"""
Admin API — Shops: list/update/moderate/requisites/detail + seller KYC verifications.

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


@router.get("/shops", response_model=dict)
async def list_shops(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    is_active: Optional[bool] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
):
    query = select(Shop)
    if q:
        query = query.where(Shop.name.ilike(f"%{q}%"))
    if is_active is not None:
        query = query.where(Shop.is_active == is_active)
    if status_filter:
        query = query.where(Shop.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    result = await db.execute(query.order_by(Shop.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    shops = result.scalars().all()
    return {"items": [ShopOut.model_validate(s) for s in shops], "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.patch("/shops/{shop_id}", response_model=ShopOut)
async def update_shop(
    shop_id: int,
    payload: ShopAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator_or_admin),
):
    result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(shop, field, value)
    from app.services.audit_service import log_action
    await log_action(db, current_user.id, "shop.update", "shop", shop.id, detail=", ".join(data.keys()))
    await db.commit()
    await db.refresh(shop)
    return shop


@router.post("/shops/{shop_id}/moderate", response_model=ShopOut)
async def moderate_shop(
    shop_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator_or_admin),
):
    """
    Approve, reject, or suspend a shop. Rejection/suspension require a reason.
    Records the decision in the audit log and notifies the owner.
    """
    from app.models.models import ShopStatus, NotificationType
    from app.services.notification_service import notify
    from app.services.audit_service import log_action

    new_status = payload.get("status")
    reason = payload.get("moderation_reason")
    if new_status not in ("active", "rejected", "suspended", "pending"):
        raise HTTPException(status_code=400, detail="Недопустимый статус")
    if new_status in ("rejected", "suspended") and not reason:
        raise HTTPException(status_code=400, detail="Укажите причину")

    shop = (await db.execute(select(Shop).where(Shop.id == shop_id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Магазин не найден")

    shop.status = ShopStatus(new_status)
    shop.moderation_reason = reason
    if new_status in ("rejected", "suspended"):
        shop.is_active = False
    elif new_status == "active":
        shop.is_active = True

    await log_action(db, current_user.id, f"shop.{new_status}", "shop", shop.id, detail=reason)
    await notify(
        db, shop.owner_id, NotificationType.system,
        title=f"Магазин: {new_status}",
        body=reason or f"Статус вашего магазина изменён на «{new_status}»",
        link="/seller/shop", send_email=True,
    )
    await db.commit()
    await db.refresh(shop)
    return shop


@router.get("/shops/{shop_id}/requisites")
async def get_shop_requisites(
    shop_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """View a shop's tax requisites (for moderation/compliance)."""
    from app.models.models import SellerRequisites
    req = (await db.execute(
        select(SellerRequisites).where(SellerRequisites.shop_id == shop_id)
    )).scalar_one_or_none()
    if not req:
        return None
    return {
        "tax_regime": req.tax_regime.value,
        "legal_name": req.legal_name,
        "inn": req.inn,
        "ogrn": req.ogrn,
        "kpp": req.kpp,
        "legal_address": req.legal_address,
        "bank_account": req.bank_account,
        "bank_name": req.bank_name,
        "bik": req.bik,
        "corr_account": req.corr_account,
    }


@router.get("/shops/{shop_id}/detail")
async def shop_detail(
    shop_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """360° view of a shop: owner, lifetime sales/fees/net, payouts, product
    counts and recent orders containing this shop's items."""
    from app.models.models import Order, OrderItem, PayoutRequest

    shop = (await db.execute(select(Shop).where(Shop.id == shop_id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Магазин не найден")

    def _sum(v) -> Decimal:
        return Decimal(str(v or 0))

    owner = (await db.execute(select(User).where(User.id == shop.owner_id))).scalar_one_or_none()

    products_count = (await db.execute(
        select(func.count(Product.id)).where(Product.shop_id == shop_id)
    )).scalar_one()

    # Lifetime financials from this shop's order items (multi-shop safe).
    gross = _sum((await db.execute(
        select(func.sum(OrderItem.price_at_time * OrderItem.quantity)).where(OrderItem.shop_id == shop_id)
    )).scalar_one())
    fees = _sum((await db.execute(
        select(func.sum(OrderItem.platform_fee)).where(OrderItem.shop_id == shop_id)
    )).scalar_one())
    net = _sum((await db.execute(
        select(func.sum(OrderItem.seller_net)).where(OrderItem.shop_id == shop_id)
    )).scalar_one())
    orders_count = (await db.execute(
        select(func.count(func.distinct(OrderItem.order_id))).where(OrderItem.shop_id == shop_id)
    )).scalar_one()

    payouts_paid = _sum((await db.execute(
        select(func.sum(PayoutRequest.amount)).where(
            PayoutRequest.user_id == shop.owner_id,
            PayoutRequest.source == "sales", PayoutRequest.status == "paid")
    )).scalar_one())

    recent_order_ids = [row[0] for row in (await db.execute(
        select(OrderItem.order_id).where(OrderItem.shop_id == shop_id)
        .distinct().order_by(OrderItem.order_id.desc()).limit(10)
    )).all()]
    recent_orders = []
    if recent_order_ids:
        rows = (await db.execute(
            select(Order).where(Order.id.in_(recent_order_ids)).order_by(Order.created_at.desc())
        )).scalars().all()
        recent_orders = [
            {"id": o.id, "total_price": o.total_price,
             "status": str(o.status.value if hasattr(o.status, "value") else o.status),
             "created_at": o.created_at.isoformat()} for o in rows
        ]

    return {
        "shop": ShopOut.model_validate(shop),
        "owner": None if not owner else {
            "id": owner.id, "email": owner.email, "full_name": owner.full_name,
            "role": owner.role.value if hasattr(owner.role, "value") else owner.role,
            "balance": owner.balance,
        },
        "stats": {
            "products_count": products_count,
            "orders_count": orders_count,
            "gross_sales": gross,
            "platform_fees": fees,
            "seller_net": net,
            "payouts_paid": payouts_paid,
            "owed_balance": owner.balance if owner else Decimal("0"),
        },
        "recent_orders": recent_orders,
    }


# ─── Seller KYC verification ───────────────────────────────────────────────────

@router.get("/verifications")
async def list_verifications(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    status_filter: Optional[str] = Query("pending", alias="status"),
):
    import json
    from app.models.models import SellerVerification
    query = select(SellerVerification, Shop).join(Shop, Shop.id == SellerVerification.shop_id)
    if status_filter:
        query = query.where(SellerVerification.status == status_filter)
    rows = (await db.execute(query.order_by(SellerVerification.submitted_at.desc()))).all()
    return [
        {"shop_id": v.shop_id, "shop_name": s.name,
         "status": v.status.value if hasattr(v.status, "value") else v.status,
         "note": v.note, "reason": v.reason,
         "documents": json.loads(v.document_keys) if v.document_keys else [],
         "submitted_at": v.submitted_at.isoformat()}
        for v, s in rows
    ]


@router.post("/verifications/{shop_id}/review")
async def review_verification(
    shop_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator_or_admin),
):
    from app.services.trust_service import review_kyc
    from app.services.audit_service import log_action
    from app.services.notification_service import notify
    from app.models.models import NotificationType, Shop as _Shop
    approve = bool(payload.get("approve"))
    reason = payload.get("reason") or ""
    if not approve and not reason:
        raise HTTPException(status_code=400, detail="Укажите причину отклонения")
    try:
        rec = await review_kyc(db, shop_id, approve, current_user.id, reason)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await log_action(db, current_user.id, f"kyc.{'approved' if approve else 'rejected'}", "shop", shop_id, detail=reason)
    shop = (await db.execute(select(_Shop).where(_Shop.id == shop_id))).scalar_one_or_none()
    if shop:
        await notify(
            db, shop.owner_id, NotificationType.system,
            title="Верификация: " + ("одобрена" if approve else "отклонена"),
            body=reason or ("Магазин получил бейдж «Проверенный»" if approve else ""),
            link="/seller/trust", send_email=True,
        )
    await db.commit()
    return {"status": rec.status.value if hasattr(rec.status, "value") else rec.status}


# ─── Marketing campaigns (email / in-app broadcasts) ───────────────────────────

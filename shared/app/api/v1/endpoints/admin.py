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
    FeatureFlagOut, FeatureFlagUpsert, UserPermissionsUpdate,
)
from app.services import fiscal_service
from app.services.settings_service import get_all_settings, set_setting

router = APIRouter(prefix="/admin", tags=["admin"])

# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total_orders = (await db.execute(select(func.count(Order.id)))).scalar_one()
    orders_today = (await db.execute(
        select(func.count(Order.id)).where(Order.created_at >= today_start)
    )).scalar_one()

    revenue_row = await db.execute(
        select(func.coalesce(func.sum(Order.total_price), 0))
        .where(Order.status.in_([OrderStatus.paid, OrderStatus.completed, OrderStatus.shipped, OrderStatus.delivered]))
    )
    total_revenue = Decimal(str(revenue_row.scalar_one()))

    revenue_today_row = await db.execute(
        select(func.coalesce(func.sum(Order.total_price), 0))
        .where(
            Order.status.in_([OrderStatus.paid, OrderStatus.completed, OrderStatus.shipped, OrderStatus.delivered]),
            Order.created_at >= today_start,
        )
    )
    revenue_today = Decimal(str(revenue_today_row.scalar_one()))

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    new_users_today = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= today_start)
    )).scalar_one()

    total_products = (await db.execute(select(func.count(Product.id)))).scalar_one()
    pending_mod = (await db.execute(
        select(func.count(Product.id)).where(Product.status == ProductStatus.pending)
    )).scalar_one()

    open_reports = (await db.execute(
        select(func.count()).where(Report.status == ReportStatus.open)
    )).scalar_one()

    return DashboardStats(
        total_orders=total_orders,
        orders_today=orders_today,
        total_revenue=total_revenue,
        revenue_today=revenue_today,
        total_users=total_users,
        new_users_today=new_users_today,
        total_products=total_products,
        pending_moderation=pending_mod,
        open_reports=open_reports,
    )


# ─── Users ────────────────────────────────────────────────────────────────────

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

    # Only superadmin can change roles
    if payload.role is not None and current_user.role != UserRole.superadmin:
        raise HTTPException(status_code=403, detail="Only superadmin can change roles")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


# ─── Shops ────────────────────────────────────────────────────────────────────

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
    _: User = Depends(get_current_moderator_or_admin),
):
    result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(shop, field, value)
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


# ─── Products (moderation) ────────────────────────────────────────────────────

@router.get("/products", response_model=dict)
async def list_products_admin(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = None,
):
    query = select(Product).options(selectinload(Product.images))
    if status_filter:
        query = query.where(Product.status == status_filter)
    if q:
        query = query.where(Product.title.ilike(f"%{q}%"))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    result = await db.execute(query.order_by(Product.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    products = result.scalars().all()
    return {"items": [ProductOut.model_validate(p) for p in products], "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.patch("/products/{product_id}/moderate", response_model=ProductOut)
async def moderate_product(
    product_id: int,
    payload: ProductModerationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator_or_admin),
):
    result = await db.execute(select(Product).options(selectinload(Product.images)).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if payload.status == ProductStatus.rejected and not payload.moderation_reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")
    product.status = payload.status
    product.moderation_reason = payload.moderation_reason

    from app.services.audit_service import log_action
    from app.services.notification_service import notify
    from app.models.models import Shop, NotificationType
    await log_action(
        db, current_user.id, f"product.{payload.status.value}", "product", product.id,
        detail=payload.moderation_reason,
    )
    # Notify the shop owner of the decision
    shop = (await db.execute(select(Shop).where(Shop.id == product.shop_id))).scalar_one_or_none()
    if shop:
        await notify(
            db, shop.owner_id, NotificationType.system,
            title=f"Товар: {payload.status.value}",
            body=f"«{product.title}» — {payload.moderation_reason or payload.status.value}",
            link="/seller/products", send_email=False,
        )
    await db.commit()
    await db.refresh(product)
    return product


@router.post("/products/bulk-moderate")
async def bulk_moderate(
    product_ids: list[int],
    new_status: ProductStatus,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator_or_admin),
):
    if new_status == ProductStatus.rejected and not reason:
        raise HTTPException(status_code=400, detail="Rejection reason required")
    await db.execute(
        update(Product)
        .where(Product.id.in_(product_ids))
        .values(status=new_status, moderation_reason=reason)
    )
    from app.services.audit_service import log_action
    await log_action(
        db, current_user.id, f"product.bulk_{new_status.value}", "product", None,
        detail=f"{len(product_ids)} товаров; {reason or ''}",
    )
    await db.commit()
    return {"updated": len(product_ids)}


@router.get("/moderation/queue")
async def moderation_queue(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """
    Pending products enriched with auto-flags and a priority score, sorted so
    the items most likely to need attention come first.
    """
    from app.models.models import Shop
    from app.services.moderation_service import (
        compute_flags, priority_from_flags, category_avg_price,
    )

    pending = (await db.execute(
        select(Product).where(Product.status == ProductStatus.pending)
        .order_by(Product.created_at)
    )).scalars().all()

    avg_cache: dict[int, object] = {}
    items = []
    for p in pending:
        if p.category_id not in avg_cache:
            avg_cache[p.category_id] = await category_avg_price(db, p.category_id)
        flags = await compute_flags(p, db, avg_cache[p.category_id])
        priority = priority_from_flags(flags, p.created_at)
        shop = (await db.execute(select(Shop).where(Shop.id == p.shop_id))).scalar_one_or_none()
        items.append({
            "product_id": p.id,
            "title": p.title,
            "shop_id": p.shop_id,
            "shop_name": shop.name if shop else None,
            "price": float(p.price),
            "created_at": p.created_at.isoformat(),
            "priority": priority,
            "flags": flags,
        })
    items.sort(key=lambda x: (-x["priority"], x["created_at"]))
    return items


@router.get("/audit-log")
async def view_audit_log(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Browse the audit log (most recent first), optionally filtered."""
    from app.models.models import AuditLog
    query = select(AuditLog)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(
        query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    # Resolve actor emails in one pass
    actor_ids = {r.actor_id for r in rows if r.actor_id}
    emails = {}
    if actor_ids:
        users = (await db.execute(select(User).where(User.id.in_(actor_ids)))).scalars().all()
        emails = {u.id: u.email for u in users}

    return {
        "items": [
            {
                "id": r.id, "actor_id": r.actor_id, "actor_email": emails.get(r.actor_id),
                "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id,
                "detail": r.detail, "created_at": r.created_at.isoformat(),
            } for r in rows
        ],
        "total": total, "page": page, "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


# ─── Reviews (moderation) ──────────────────────────────────────────────────────

@router.get("/reviews", response_model=dict)
async def list_reviews_admin(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    from sqlalchemy.orm import selectinload
    query = select(Review).options(
        selectinload(Review.user), selectinload(Review.reply), selectinload(Review.votes)
    )
    if status_filter:
        query = query.where(Review.status == status_filter)
    query = query.order_by(Review.created_at.desc())

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    reviews = result.scalars().all()
    return {
        "items": [ReviewOut.model_validate(r) for r in reviews],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.patch("/reviews/{review_id}/moderate", response_model=ReviewOut)
async def moderate_review(
    review_id: int,
    payload: ReviewModerationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator_or_admin),
):
    from sqlalchemy.orm import selectinload
    from datetime import datetime, timezone
    from app.services.settings_service import get_setting

    result = await db.execute(
        select(Review)
        .options(selectinload(Review.user), selectinload(Review.reply), selectinload(Review.votes))
        .where(Review.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if payload.status == ReviewStatus.rejected and not payload.moderation_reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    review.status = payload.status
    review.moderation_reason = payload.moderation_reason
    review.moderated_by_id = current_user.id
    review.moderated_at = datetime.now(timezone.utc)
    await db.flush()

    # Recalculate product + seller ratings using only approved reviews
    from app.services import rating_service
    await rating_service.recalculate_for_product(db, review.product_id)

    await db.commit()
    await db.refresh(review)
    return review


@router.delete("/reviews/{review_id}", status_code=204)
async def delete_review_admin(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    product_id = review.product_id
    await db.delete(review)
    await db.flush()

    from app.services import rating_service
    await rating_service.recalculate_for_product(db, product_id)
    await db.commit()


# ─── Orders ───────────────────────────────────────────────────────────────────

@router.get("/orders", response_model=dict)
async def list_orders_admin(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = None,
):
    query = select(Order).options(
        selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.images),
        selectinload(Order.payment),
        selectinload(Order.delivery_info),
    )
    if status_filter:
        query = query.where(Order.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    result = await db.execute(query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    orders = result.scalars().all()
    return {"items": [OrderOut.model_validate(o) for o in orders], "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
async def update_order_admin(
    order_id: int,
    payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.services.payout_service import payout_sellers_for_order, refund_sellers_for_order
    from app.services.referral_service import process_buyer_referral_reward, process_seller_referral_reward

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.images), selectinload(Order.payment), selectinload(Order.delivery_info))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    previous_status = order.status
    order.status = payload.status
    if payload.tracking_number and order.delivery_info:
        order.delivery_info.tracking_number = payload.tracking_number

    # Same payout/refund/referral side-effects as the buyer-facing endpoint,
    # so an admin manually moving an order to 'completed' or 'cancelled'
    # triggers the correct per-seller financial outcome.
    if payload.status == OrderStatus.completed:
        await payout_sellers_for_order(order, db)
        await process_buyer_referral_reward(order, db)
        await process_seller_referral_reward(order, db)
        from app.services.loyalty_service import award_cashback_for_order
        await award_cashback_for_order(order, db)

    if payload.status == OrderStatus.cancelled and previous_status == OrderStatus.paid:
        await refund_sellers_for_order(order, db)
        for item in order.items:
            item.product.quantity += item.quantity
        if order.bonus_used > 0:
            buyer_res = await db.execute(select(User).where(User.id == order.buyer_id))
            buyer = buyer_res.scalar_one_or_none()
            if buyer:
                buyer.bonus_balance += order.bonus_used

    await db.commit()
    await db.refresh(order)
    return order


@router.post("/orders/{order_id}/refund")
async def initiate_refund(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    result = await db.execute(select(Order).options(selectinload(Order.payment)).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if not order.payment or not order.payment.gateway_payment_id:
        raise HTTPException(status_code=400, detail="No payment to refund")

    from app.services.payment_service import get_payment_gateway
    gw = get_payment_gateway()
    success = await gw.refund_payment(order.payment.gateway_payment_id, order.total_price)
    if success:
        order.status = OrderStatus.refunded
        order.payment.status = PaymentStatus.refunded
        await db.commit()
        return {"status": "refunded"}
    raise HTTPException(status_code=502, detail="Refund failed at payment gateway")


# ─── Fiscalization (54-ФЗ) ─────────────────────────────────────────────────────

@router.get("/fiscal/receipts", response_model=dict)
async def list_fiscal_receipts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    status_filter: Optional[str] = Query(None, alias="status"),
    type_filter: Optional[str] = Query(None, alias="type"),
    order_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Browse fiscal receipts (most recent first), optionally filtered by status,
    type or order. Surfaces failed/pending registrations for monitoring."""
    query = select(FiscalReceipt)
    if status_filter:
        try:
            query = query.where(FiscalReceipt.status == FiscalReceiptStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail="Недопустимый статус")
    if type_filter:
        try:
            query = query.where(FiscalReceipt.type == FiscalReceiptType(type_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail="Недопустимый тип")
    if order_id:
        query = query.where(FiscalReceipt.order_id == order_id)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(
        query.order_by(FiscalReceipt.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    # Aggregate counts by status for the dashboard header.
    counts_rows = (await db.execute(
        select(FiscalReceipt.status, func.count()).group_by(FiscalReceipt.status)
    )).all()
    counts = {s.value: 0 for s in FiscalReceiptStatus}
    for st, cnt in counts_rows:
        counts[st.value if hasattr(st, "value") else st] = cnt

    return {
        "items": [FiscalReceiptOut.model_validate(r).model_dump(mode="json") for r in rows],
        "total": total, "page": page, "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "counts": counts,
    }


@router.get("/fiscal/receipts/{receipt_id}", response_model=FiscalReceiptOut)
async def get_fiscal_receipt(
    receipt_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    fr = (await db.execute(
        select(FiscalReceipt).where(FiscalReceipt.id == receipt_id)
    )).scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail="Чек не найден")
    return fr


@router.post("/fiscal/receipts/{receipt_id}/retry")
async def retry_fiscal_receipt(
    receipt_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """
    Re-register a failed/canceled receipt via YooKassa's standalone /receipts
    endpoint, referencing the original payment. Only meaningful for income
    receipts whose payment has a gateway id.
    """
    fr = (await db.execute(
        select(FiscalReceipt).options(selectinload(FiscalReceipt.payment))
        .where(FiscalReceipt.id == receipt_id)
    )).scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail="Чек не найден")
    if fr.status == FiscalReceiptStatus.succeeded:
        raise HTTPException(status_code=400, detail="Чек уже зарегистрирован")
    if not fr.payment or not fr.payment.gateway_payment_id:
        raise HTTPException(status_code=400, detail="Нет связанного платежа для повторной отправки")

    receipt = {
        "customer": fiscal_service._customer_block(fr.customer_contact),
        "items": fr.items,
    }
    if fr.tax_system_code:
        receipt["tax_system_code"] = fr.tax_system_code
    receipt_type = "payment" if fr.type == FiscalReceiptType.income else "refund"

    from app.services.payment_service import get_payment_gateway
    gw = get_payment_gateway()
    try:
        resp = await gw.create_standalone_receipt(receipt_type, fr.payment.gateway_payment_id, receipt)
        fr.status = FiscalReceiptStatus.pending
        fr.error = None
        fiscal_service.apply_registration(fr, resp.get("status"), raw=resp)
        await db.commit()
        return {"status": fr.status.value}
    except NotImplementedError:
        raise HTTPException(status_code=400, detail="Шлюз не поддерживает повторную отправку чека")
    except Exception as e:  # noqa: BLE001
        fiscal_service.mark_failed(fr, str(e))
        await db.commit()
        raise HTTPException(status_code=502, detail="Не удалось зарегистрировать чек в ОФД")


# ─── Recommendations ───────────────────────────────────────────────────────────

@router.post("/recommendations/rebuild")
async def rebuild_recommendations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """Recompute the materialized "bought together" co-purchase signal now.
    Normally this runs nightly; this endpoint forces an immediate refresh."""
    from app.services import recommendation_service
    pairs = await recommendation_service.rebuild_co_purchase(db)
    await db.commit()
    return {"status": "ok", "pairs": pairs}


# ─── Categories ───────────────────────────────────────────────────────────────

def _cat_out(c: Category) -> CategoryOut:
    """Build a CategoryOut without touching the lazy `children` relationship."""
    return CategoryOut(
        id=c.id, parent_id=c.parent_id, name=c.name, slug=c.slug,
        image=c.image, sort_order=c.sort_order, kind=c.kind, children=[],
    )


async def _unique_category_slug(db: AsyncSession, base: str, exclude_id: int | None = None) -> str:
    """Ensure the slug is unique across categories, suffixing -2, -3, ... if needed."""
    from app.services.slug_service import slugify
    base = slugify(base) or "category"
    candidate, n = base, 1
    while True:
        q = select(Category.id).where(Category.slug == candidate)
        if exclude_id is not None:
            q = q.where(Category.id != exclude_id)
        if (await db.execute(q)).scalar_one_or_none() is None:
            return candidate
        n += 1
        candidate = f"{base}-{n}"


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories_admin(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """Full category tree (any depth), built from a single flat load."""
    cats = (await db.execute(
        select(Category).order_by(Category.sort_order, Category.name)
    )).scalars().all()
    nodes = {c.id: _cat_out(c) for c in cats}
    roots: list[CategoryOut] = []
    for c in cats:
        node = nodes[c.id]
        if c.parent_id and c.parent_id in nodes:
            nodes[c.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


@router.post("/categories", response_model=CategoryOut, status_code=201)
async def create_category(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    data = payload.model_dump()
    if data.get("parent_id"):
        parent = (await db.execute(select(Category).where(Category.id == data["parent_id"]))).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=400, detail="Родительская категория не найдена")
    data["slug"] = await _unique_category_slug(db, data.get("slug") or data["name"])
    cat = Category(**data)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return _cat_out(cat)


async def _is_descendant(db: AsyncSession, candidate_parent_id: int, cat_id: int) -> bool:
    """True if candidate_parent_id is `cat_id` itself or one of its descendants
    (moving a category under its own subtree would create a cycle)."""
    current = candidate_parent_id
    seen = set()
    while current is not None and current not in seen:
        if current == cat_id:
            return True
        seen.add(current)
        current = (await db.execute(
            select(Category.parent_id).where(Category.id == current)
        )).scalar_one_or_none()
    return False


@router.put("/categories/{cat_id}", response_model=CategoryOut)
async def update_category(
    cat_id: int,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    cat = (await db.execute(select(Category).where(Category.id == cat_id))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    data = payload.model_dump(exclude_unset=True)

    # Moving the category: validate the new parent and prevent cycles.
    if "parent_id" in data and data["parent_id"] != cat.parent_id:
        new_parent = data["parent_id"]
        if new_parent is not None:
            if new_parent == cat_id or await _is_descendant(db, new_parent, cat_id):
                raise HTTPException(status_code=400, detail="Нельзя переместить категорию внутрь самой себя")
            if (await db.execute(select(Category.id).where(Category.id == new_parent))).scalar_one_or_none() is None:
                raise HTTPException(status_code=400, detail="Родительская категория не найдена")

    if "slug" in data or "name" in data:
        base = data.get("slug") or data.get("name") or cat.name
        data["slug"] = await _unique_category_slug(db, base, exclude_id=cat_id)

    for field, value in data.items():
        setattr(cat, field, value)
    await db.commit()
    await db.refresh(cat)
    return _cat_out(cat)


@router.delete("/categories/{cat_id}", status_code=204)
async def delete_category(
    cat_id: int,
    reassign_to: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """
    Delete a category. Refuses if it still has subcategories. If it has products,
    pass ?reassign_to=<other_category_id> to move them first; otherwise the
    deletion is refused so products are never orphaned.
    """
    from app.models.models import Product
    cat = (await db.execute(select(Category).where(Category.id == cat_id))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    child_count = (await db.execute(
        select(func.count()).select_from(Category).where(Category.parent_id == cat_id)
    )).scalar_one()
    if child_count:
        raise HTTPException(status_code=400, detail="Сначала удалите или перенесите подкатегории")

    product_count = (await db.execute(
        select(func.count()).select_from(Product).where(Product.category_id == cat_id)
    )).scalar_one()
    if product_count:
        if reassign_to is None:
            raise HTTPException(
                status_code=400,
                detail=f"В категории {product_count} тов. Передайте reassign_to для переноса перед удалением.",
            )
        target = (await db.execute(select(Category).where(Category.id == reassign_to))).scalar_one_or_none()
        if not target or reassign_to == cat_id:
            raise HTTPException(status_code=400, detail="Неверная категория для переноса")
        await db.execute(
            update(Product).where(Product.category_id == cat_id).values(category_id=reassign_to)
        )

    await db.delete(cat)
    await db.commit()


# ─── Reports ──────────────────────────────────────────────────────────────────

@router.get("/reports", response_model=dict)
async def list_reports(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    query = select(Report)
    if status_filter:
        query = query.where(Report.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    result = await db.execute(query.order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    reports = result.scalars().all()
    return {"items": [ReportOut.model_validate(r) for r in reports], "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.patch("/reports/{report_id}", response_model=ReportOut)
async def update_report(
    report_id: int,
    payload: ReportUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, field, value)
    await db.commit()
    await db.refresh(report)
    return report


# ─── Settings ─────────────────────────────────────────────────────────────────

@router.get("/settings", response_model=list[SettingOut])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    settings_map = await get_all_settings(db)
    await db.commit()
    return list(settings_map.values())


@router.patch("/settings/{key}", response_model=SettingOut)
async def update_setting(
    key: str,
    payload: SettingUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    setting = await set_setting(db, key, payload.value)
    await db.commit()
    await db.refresh(setting)
    return setting


@router.patch("/settings", response_model=list[SettingOut])
async def bulk_update_settings(
    payload: BulkSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    results = []
    for key, value in payload.settings.items():
        s = await set_setting(db, key, value)
        results.append(s)
    await db.commit()
    return results


# ─── Coupons ──────────────────────────────────────────────────────────────────

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
    from app.schemas.schemas import PayoutRequestOut
    query = select(PayoutRequest).order_by(PayoutRequest.created_at.desc())
    if status_filter:
        query = query.where(PayoutRequest.status == status_filter)
    result = await db.execute(query)
    return [PayoutRequestOut.model_validate(p) for p in result.scalars().all()]


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

@router.get("/banners", response_model=list)
async def list_banners_admin(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.models.models import HomepageBanner
    from app.schemas.schemas import HomepageBannerOut
    result = await db.execute(select(HomepageBanner).order_by(HomepageBanner.sort_order))
    return [HomepageBannerOut.model_validate(b) for b in result.scalars().all()]


@router.post("/banners", status_code=201)
async def create_banner(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.models.models import HomepageBanner
    from app.schemas.schemas import HomepageBannerCreate, HomepageBannerOut
    data = HomepageBannerCreate(**payload)
    banner = HomepageBanner(**data.model_dump())
    db.add(banner)
    await db.commit()
    await db.refresh(banner)
    return HomepageBannerOut.model_validate(banner)


@router.delete("/banners/{banner_id}", status_code=204)
async def delete_banner(
    banner_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.models.models import HomepageBanner
    result = await db.execute(select(HomepageBanner).where(HomepageBanner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Баннер не найден")
    await db.delete(banner)
    await db.commit()


# ─── Seller analytics ──────────────────────────────────────────────────────────

@router.get("/seller-analytics")
async def seller_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """
    Sales analytics for the current seller's shop: totals, revenue over the
    last 30 days, and top products. Reads from OrderItem rows belonging to the
    seller's shop.
    """
    from datetime import datetime, timezone, timedelta
    from app.models.models import OrderItem, Order, Product

    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    # Totals
    totals = await db.execute(
        select(
            func.count(OrderItem.id),
            func.coalesce(func.sum(OrderItem.seller_net), 0),
        ).where(OrderItem.shop_id == shop.id, OrderItem.payout_status == "paid")
    )
    items_sold, total_earned = totals.one()

    # Revenue per day for last 30 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    daily = await db.execute(
        select(
            func.date(Order.created_at).label("day"),
            func.coalesce(func.sum(OrderItem.seller_net), 0).label("revenue"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(OrderItem.shop_id == shop.id, Order.created_at >= cutoff)
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
    )
    revenue_by_day = [{"day": str(row.day), "revenue": float(row.revenue)} for row in daily]

    # Top products by quantity sold
    top = await db.execute(
        select(
            Product.title,
            func.sum(OrderItem.quantity).label("qty"),
            func.coalesce(func.sum(OrderItem.seller_net), 0).label("revenue"),
        )
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.shop_id == shop.id)
        .group_by(Product.id, Product.title)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
    )
    top_products = [{"title": row.title, "qty": int(row.qty), "revenue": float(row.revenue)} for row in top]

    return {
        "items_sold": items_sold or 0,
        "total_earned": float(total_earned or 0),
        "current_balance": float(current_user.balance),
        "revenue_by_day": revenue_by_day,
        "top_products": top_products,
    }


# ─── Platform analytics (item 12) ────────────────────────────────────────────────

@router.get("/platform-analytics")
async def platform_analytics(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """
    Platform-wide analytics dashboard: GMV, order/revenue trends over the last
    30 days, top shops by sales, and new-user growth.
    """
    from app.models.models import Order, OrderItem, Shop, Product

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # GMV = sum of completed order subtotals
    gmv_row = await db.execute(
        select(func.coalesce(func.sum(Order.subtotal), 0))
        .where(Order.status.in_([OrderStatus.completed, OrderStatus.delivered]))
    )
    gmv = float(gmv_row.scalar_one())

    # Platform commission earned
    fee_row = await db.execute(
        select(func.coalesce(func.sum(OrderItem.platform_fee), 0))
        .where(OrderItem.payout_status == "paid")
    )
    platform_revenue = float(fee_row.scalar_one())

    # Orders + revenue per day (last 30d)
    daily = await db.execute(
        select(
            func.date(Order.created_at).label("day"),
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.subtotal), 0).label("revenue"),
        )
        .where(Order.created_at >= cutoff)
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
    )
    trend = [{"day": str(r.day), "orders": r.orders, "revenue": float(r.revenue)} for r in daily]

    # Top shops by sales
    top_shops = await db.execute(
        select(
            Shop.name,
            func.coalesce(func.sum(OrderItem.seller_net), 0).label("net"),
            func.count(OrderItem.id).label("items"),
        )
        .join(Shop, Shop.id == OrderItem.shop_id)
        .group_by(Shop.id, Shop.name)
        .order_by(func.coalesce(func.sum(OrderItem.seller_net), 0).desc())
        .limit(10)
    )
    shops = [{"name": r.name, "net": float(r.net), "items": r.items} for r in top_shops]

    # New users per day
    new_users = await db.execute(
        select(func.date(User.created_at).label("day"), func.count(User.id).label("count"))
        .where(User.created_at >= cutoff)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
    )
    user_growth = [{"day": str(r.day), "count": r.count} for r in new_users]

    return {
        "gmv": gmv,
        "platform_revenue": platform_revenue,
        "trend": trend,
        "top_shops": shops,
        "user_growth": user_growth,
    }


# ─── Currency management (item 11) ───────────────────────────────────────────────

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

@router.get("/returns")
async def admin_list_returns(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    from app.models.models import ReturnRequest
    from app.schemas.schemas import ReturnRequestOut
    q = select(ReturnRequest).order_by(ReturnRequest.created_at.desc())
    if status_filter:
        q = q.where(ReturnRequest.status == status_filter)
    result = await db.execute(q)
    return [ReturnRequestOut.model_validate(r) for r in result.scalars().all()]


# ─── Block 5: cohort analytics, RBAC, reconciliation, feature flags ───────────────

@router.get("/analytics/cohorts")
async def analytics_cohorts(
    months: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.services.analytics_service import cohort_retention
    return await cohort_retention(db, months)


@router.get("/analytics/ltv")
async def analytics_ltv(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.services.analytics_service import lifetime_value
    return await lifetime_value(db)


@router.get("/analytics/funnel")
async def analytics_funnel(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.services.analytics_service import conversion_funnel
    return await conversion_funnel(db, days)


@router.get("/analytics/reconciliation")
async def analytics_reconciliation(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.services.analytics_service import financial_reconciliation
    return await financial_reconciliation(db)


# ─── Audit log export ─────────────────────────────────────────────────────────────

@router.get("/audit-log/export")
async def export_audit_log(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """Export the full audit log as a CSV download."""
    import csv
    import io
    from fastapi.responses import StreamingResponse
    from app.models.models import AuditLog

    rows = (await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10000)
    )).scalars().all()

    actor_ids = {r.actor_id for r in rows if r.actor_id}
    emails = {}
    if actor_ids:
        users = (await db.execute(select(User).where(User.id.in_(actor_ids)))).scalars().all()
        emails = {u.id: u.email for u in users}

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "time", "actor", "action", "entity_type", "entity_id", "detail"])
    for r in rows:
        writer.writerow([
            r.id, r.created_at.isoformat(), emails.get(r.actor_id, ""),
            r.action, r.entity_type, r.entity_id or "", r.detail or "",
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-log.csv"},
    )


# ─── Feature flags ─────────────────────────────────────────────────────────────────

@router.get("/feature-flags", response_model=list[FeatureFlagOut])
async def list_feature_flags(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.models.models import FeatureFlag
    rows = (await db.execute(select(FeatureFlag).order_by(FeatureFlag.key))).scalars().all()
    return rows


@router.put("/feature-flags", response_model=FeatureFlagOut)
async def upsert_feature_flag(
    payload: FeatureFlagUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    from app.models.models import FeatureFlag
    from app.services.audit_service import log_action
    existing = (await db.execute(
        select(FeatureFlag).where(FeatureFlag.key == payload.key)
    )).scalar_one_or_none()
    if existing:
        existing.description = payload.description
        existing.is_enabled = payload.is_enabled
        existing.rollout_percent = payload.rollout_percent
        flag = existing
    else:
        flag = FeatureFlag(**payload.model_dump())
        db.add(flag)
    await log_action(db, current_user.id, "feature_flag.upsert", "feature_flag", None, detail=payload.key)
    await db.commit()
    await db.refresh(flag)
    return flag


@router.delete("/feature-flags/{flag_id}", status_code=204)
async def delete_feature_flag(
    flag_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    from app.models.models import FeatureFlag
    flag = (await db.execute(select(FeatureFlag).where(FeatureFlag.id == flag_id))).scalar_one_or_none()
    if not flag:
        raise HTTPException(status_code=404, detail="Флаг не найден")
    await db.delete(flag)
    await db.commit()


# ─── RBAC: granular permissions ────────────────────────────────────────────────────

@router.get("/permissions/catalog")
async def permissions_catalog(_: User = Depends(get_current_superadmin)):
    """The full catalog of grantable permissions (key -> description)."""
    from app.services.rbac_service import ALL_PERMISSIONS
    return [{"key": k, "description": v} for k, v in ALL_PERMISSIONS.items()]


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

@router.get("/sms/status")
async def sms_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """Current SMS config (without exposing the raw password) + live balance."""
    from app.services.settings_service import get_setting
    from app.services.sms_service import get_balance

    enabled = (await get_setting(db, "sms_enabled")).lower() == "true"
    login = await get_setting(db, "smsc_login")
    sender = await get_setting(db, "smsc_sender")
    use_apikey = (await get_setting(db, "smsc_use_apikey")).lower() == "true"
    password = await get_setting(db, "smsc_password")

    balance = await get_balance(db) if (login or use_apikey) and password else {
        "ok": False, "balance": None, "currency": None, "error": "Учётные данные не заданы"
    }
    return {
        "enabled": enabled,
        "login": login,
        "sender": sender,
        "use_apikey": use_apikey,
        "has_password": bool(password),
        "notify_order_status": (await get_setting(db, "sms_notify_order_status")).lower() == "true",
        "notify_phone_verification": (await get_setting(db, "sms_notify_phone_verification")).lower() == "true",
        "balance": balance,
    }


@router.put("/sms/settings")
async def update_sms_settings(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Update SMS settings from the dedicated admin section."""
    from app.services.settings_service import set_setting
    from app.services.audit_service import log_action

    allowed = {
        "sms_enabled", "smsc_login", "smsc_password", "smsc_sender",
        "smsc_use_apikey", "sms_notify_order_status", "sms_notify_phone_verification",
    }
    for key, value in payload.items():
        if key not in allowed:
            continue
        # Don't overwrite the stored password with an empty/masked value
        if key == "smsc_password" and value in ("", None, "********"):
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        await set_setting(db, key, str(value))

    await log_action(db, current_user.id, "sms.settings_update", "settings", None,
                     detail="SMS section updated")
    await db.commit()
    return {"status": "saved"}


@router.post("/sms/test")
async def sms_test(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Send a test SMS to verify credentials (bypasses the enabled gate)."""
    from app.services.sms_service import send_sms
    phone = payload.get("phone")
    if not phone:
        raise HTTPException(status_code=400, detail="Укажите номер телефона")
    text = payload.get("text") or "Тестовое сообщение от маркетплейса"
    result = await send_sms(db, phone, text, purpose="test", force=True)
    await db.commit()
    return result


@router.get("/sms/balance")
async def sms_balance(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """Live SMSC.ru account balance."""
    from app.services.sms_service import get_balance
    return await get_balance(db)


@router.get("/sms/stats")
async def sms_stats(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """SMS statistics: totals, success rate, spend, breakdown by purpose."""
    from datetime import datetime, timezone, timedelta
    from app.models.models import SmsLog
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (await db.execute(
        select(SmsLog).where(SmsLog.created_at >= cutoff)
    )).scalars().all()

    total = len(rows)
    sent = sum(1 for r in rows if r.status == "sent")
    failed = total - sent
    total_cost = sum(float(r.cost) for r in rows if r.cost is not None)
    total_segments = sum(r.sms_count for r in rows if r.status == "sent")

    by_purpose: dict[str, dict] = {}
    for r in rows:
        p = by_purpose.setdefault(r.purpose, {"sent": 0, "failed": 0, "cost": 0.0})
        if r.status == "sent":
            p["sent"] += 1
            p["cost"] += float(r.cost) if r.cost else 0.0
        else:
            p["failed"] += 1

    return {
        "days": days,
        "total": total,
        "sent": sent,
        "failed": failed,
        "success_rate": round(sent / total * 100, 1) if total else 0.0,
        "total_cost": round(total_cost, 2),
        "total_segments": total_segments,
        "by_purpose": by_purpose,
    }


@router.get("/sms/log")
async def sms_log_view(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """Recent SMS send log."""
    from app.models.models import SmsLog
    query = select(SmsLog)
    if status_filter:
        query = query.where(SmsLog.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(
        query.order_by(SmsLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {
        "items": [
            {
                "id": r.id, "phone": r.phone, "purpose": r.purpose,
                "text_preview": r.text_preview, "status": r.status,
                "smsc_id": r.smsc_id, "cost": float(r.cost) if r.cost else None,
                "sms_count": r.sms_count, "error": r.error,
                "created_at": r.created_at.isoformat(),
            } for r in rows
        ],
        "total": total, "page": page, "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }

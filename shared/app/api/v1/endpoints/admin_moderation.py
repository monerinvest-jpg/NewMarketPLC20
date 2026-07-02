"""
Admin API — Moderation: products (single/bulk), the queue, reviews, user reports, audit log (+export).

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

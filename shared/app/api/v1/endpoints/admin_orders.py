"""
Admin API — Orders: list/status/refund, 54-FZ fiscal receipts, returns.

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
    current_user: User = Depends(get_current_moderator_or_admin),
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
    terminal = (OrderStatus.cancelled, OrderStatus.refunded)
    order.status = payload.status
    if payload.tracking_number is not None and order.delivery_info:
        order.delivery_info.tracking_number = payload.tracking_number
    if payload.delivery_address is not None:
        order.delivery_address = payload.delivery_address

    # Same payout/refund/referral side-effects as the buyer-facing endpoint,
    # so an admin manually moving an order to 'completed' or 'cancelled'
    # triggers the correct per-seller financial outcome.
    if payload.status == OrderStatus.completed and previous_status != OrderStatus.completed:
        await payout_sellers_for_order(order, db)
        await process_buyer_referral_reward(order, db)
        await process_seller_referral_reward(order, db)
        from app.services.loyalty_service import award_cashback_for_order
        await award_cashback_for_order(order, db)

    # Comprehensive reversal (stock + bonus + promo + referral balances + seller
    # refund + revoked digital entitlements) when cancelling/refunding a live order.
    if payload.status in terminal and previous_status not in terminal:
        from app.services.order_reversal_service import restore_order
        await restore_order(db, order)

    from app.services.audit_service import log_action
    await log_action(
        db, current_user.id, "order.update", "order", order.id,
        detail=f"{previous_status} → {payload.status}",
    )
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

"""
Admin API — Dashboards & analytics: main dashboard, seller/platform analytics, cohorts/LTV/funnel/reconciliation.

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

    # ── Financial summary: payouts, liabilities, referral cost, net profit ──────
    from app.models.models import PayoutRequest, ReferralReward, UserRole

    def _f(v) -> float:
        return float(v or 0)

    payouts_paid = _f((await db.execute(
        select(func.sum(PayoutRequest.amount)).where(PayoutRequest.status == "paid")
    )).scalar_one())
    payouts_pending = _f((await db.execute(
        select(func.sum(PayoutRequest.amount)).where(PayoutRequest.status.in_(["pending", "approved"]))
    )).scalar_one())
    ref_payouts_paid = _f((await db.execute(
        select(func.sum(PayoutRequest.amount)).where(
            PayoutRequest.status == "paid", PayoutRequest.source == "referral")
    )).scalar_one())
    referral_cost = _f((await db.execute(
        select(func.sum(ReferralReward.amount))
    )).scalar_one())

    # Outstanding liabilities owed to users (money we still hold on their balances)
    seller_balance_liab = _f((await db.execute(
        select(func.sum(User.balance))
    )).scalar_one())
    referral_balance_liab = _f((await db.execute(
        select(func.sum(User.referral_balance))
    )).scalar_one())
    bonus_liab = _f((await db.execute(
        select(func.sum(User.bonus_balance))
    )).scalar_one())

    # Net platform profit ≈ commission earned − referral programme cost.
    net_profit = round(platform_revenue - referral_cost, 2)

    return {
        "gmv": gmv,
        "platform_revenue": platform_revenue,
        "trend": trend,
        "top_shops": shops,
        "user_growth": user_growth,
        "finance": {
            "platform_commission": round(platform_revenue, 2),
            "referral_cost": round(referral_cost, 2),
            "net_profit": net_profit,
            "payouts_paid": round(payouts_paid, 2),
            "payouts_pending": round(payouts_pending, 2),
            "referral_payouts_paid": round(ref_payouts_paid, 2),
            "liabilities": {
                "seller_balances": round(seller_balance_liab, 2),
                "referral_balances": round(referral_balance_liab, 2),
                "bonus_balances": round(bonus_liab, 2),
                "pending_payouts": round(payouts_pending, 2),
            },
        },
    }


# ─── Currency management (item 11) ───────────────────────────────────────────────

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

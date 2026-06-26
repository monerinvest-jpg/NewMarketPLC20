"""
Analytics service. Heavier read-only aggregations for the admin dashboards:
cohort retention, lifetime value, a simple conversion funnel, and a financial
reconciliation summary. All queries are scoped platform-wide.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    BalanceTransaction, Order, OrderItem, OrderStatus, Payment, PaymentStatus,
    PayoutRequest, PayoutRequestStatus, ProductView, ReturnRequest,
    ReturnRequestStatus, User,
)


async def cohort_retention(db: AsyncSession, months: int = 6) -> dict:
    """
    Monthly signup cohorts and how many of each cohort placed an order in the
    following months. Returns a matrix usable for a retention heatmap.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=31 * months)

    # Cohort = month of signup; map user_id -> cohort label
    users = (await db.execute(
        select(User.id, User.created_at).where(User.created_at >= cutoff)
    )).all()
    cohorts: dict[str, list[int]] = {}
    user_cohort: dict[int, str] = {}
    for uid, created in users:
        label = created.strftime("%Y-%m")
        cohorts.setdefault(label, []).append(uid)
        user_cohort[uid] = label

    # Orders by these users
    user_ids = list(user_cohort.keys())
    rows = []
    if user_ids:
        rows = (await db.execute(
            select(Order.buyer_id, Order.created_at)
            .where(Order.buyer_id.in_(user_ids))
        )).all()

    # matrix[cohort][month_offset] = set of active users
    matrix: dict[str, dict[int, set]] = {c: {} for c in cohorts}
    for buyer_id, created in rows:
        c = user_cohort.get(buyer_id)
        if not c:
            continue
        cohort_start = datetime.strptime(c, "%Y-%m").replace(tzinfo=timezone.utc)
        offset = (created.year - cohort_start.year) * 12 + (created.month - cohort_start.month)
        if offset >= 0:
            matrix[c].setdefault(offset, set()).add(buyer_id)

    result = []
    for cohort in sorted(cohorts):
        size = len(cohorts[cohort])
        offsets = matrix[cohort]
        max_off = max(offsets.keys()) if offsets else 0
        retention = []
        for off in range(max_off + 1):
            active = len(offsets.get(off, set()))
            retention.append({
                "offset": off,
                "active": active,
                "percent": round(active / size * 100, 1) if size else 0.0,
            })
        result.append({"cohort": cohort, "size": size, "retention": retention})
    return {"cohorts": result}


async def lifetime_value(db: AsyncSession) -> dict:
    """
    Aggregate LTV stats: average revenue per buyer, top buyers, and overall.
    Uses completed/delivered orders as realized revenue.
    """
    realized = [OrderStatus.completed, OrderStatus.delivered]

    per_buyer = (await db.execute(
        select(
            Order.buyer_id,
            func.sum(Order.subtotal).label("revenue"),
            func.count(Order.id).label("orders"),
        )
        .where(Order.status.in_(realized))
        .group_by(Order.buyer_id)
    )).all()

    if not per_buyer:
        return {"avg_ltv": 0.0, "avg_orders": 0.0, "buyer_count": 0, "top_buyers": []}

    revenues = [float(r.revenue or 0) for r in per_buyer]
    orders = [r.orders for r in per_buyer]
    avg_ltv = sum(revenues) / len(revenues)
    avg_orders = sum(orders) / len(orders)

    # Resolve emails for top buyers
    top = sorted(per_buyer, key=lambda r: float(r.revenue or 0), reverse=True)[:10]
    top_ids = [r.buyer_id for r in top]
    emails = {}
    if top_ids:
        users = (await db.execute(select(User).where(User.id.in_(top_ids)))).scalars().all()
        emails = {u.id: u.email for u in users}

    return {
        "avg_ltv": round(avg_ltv, 2),
        "avg_orders": round(avg_orders, 2),
        "buyer_count": len(per_buyer),
        "top_buyers": [
            {"email": emails.get(r.buyer_id, f"#{r.buyer_id}"),
             "revenue": float(r.revenue or 0), "orders": r.orders}
            for r in top
        ],
    }


async def conversion_funnel(db: AsyncSession, days: int = 30) -> dict:
    """
    A simple funnel over a recent window: distinct product viewers -> buyers
    who created an order -> buyers whose order was paid.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    viewers = (await db.execute(
        select(func.count(func.distinct(ProductView.user_id)))
        .where(ProductView.viewed_at >= cutoff)
    )).scalar_one()

    order_creators = (await db.execute(
        select(func.count(func.distinct(Order.buyer_id)))
        .where(Order.created_at >= cutoff)
    )).scalar_one()

    paid_buyers = (await db.execute(
        select(func.count(func.distinct(Order.buyer_id)))
        .where(
            Order.created_at >= cutoff,
            Order.status.notin_([OrderStatus.pending_payment, OrderStatus.cancelled]),
        )
    )).scalar_one()

    def pct(n, base):
        return round(n / base * 100, 1) if base else 0.0

    return {
        "stages": [
            {"stage": "Просмотрели товары", "count": viewers, "percent": 100.0},
            {"stage": "Создали заказ", "count": order_creators, "percent": pct(order_creators, viewers)},
            {"stage": "Оплатили", "count": paid_buyers, "percent": pct(paid_buyers, viewers)},
        ]
    }


async def financial_reconciliation(db: AsyncSession) -> dict:
    """
    A reconciliation summary so finance can sanity-check money flows:
    gross sales, platform commission, seller net, refunds, payouts pending/paid,
    and an outstanding-liability figure (what the platform still owes sellers).
    """
    realized = [OrderStatus.completed, OrderStatus.delivered]

    gross = (await db.execute(
        select(func.coalesce(func.sum(Order.subtotal), 0)).where(Order.status.in_(realized))
    )).scalar_one()

    commission = (await db.execute(
        select(func.coalesce(func.sum(OrderItem.platform_fee), 0))
        .where(OrderItem.payout_status == "paid")
    )).scalar_one()

    seller_net_paid = (await db.execute(
        select(func.coalesce(func.sum(OrderItem.seller_net), 0))
        .where(OrderItem.payout_status == "paid")
    )).scalar_one()

    seller_net_pending = (await db.execute(
        select(func.coalesce(func.sum(OrderItem.seller_net), 0))
        .where(OrderItem.payout_status == "pending")
    )).scalar_one()

    refunds = (await db.execute(
        select(func.coalesce(func.sum(ReturnRequest.refund_amount), 0))
        .where(ReturnRequest.status == ReturnRequestStatus.refunded)
    )).scalar_one()

    payouts_paid = (await db.execute(
        select(func.coalesce(func.sum(PayoutRequest.amount), 0))
        .where(PayoutRequest.status == PayoutRequestStatus.paid)
    )).scalar_one()

    payouts_pending = (await db.execute(
        select(func.coalesce(func.sum(PayoutRequest.amount), 0))
        .where(PayoutRequest.status == PayoutRequestStatus.pending)
    )).scalar_one()

    return {
        "gross_sales": float(gross),
        "platform_commission": float(commission),
        "seller_net_paid": float(seller_net_paid),
        "seller_net_pending": float(seller_net_pending),
        "refunds_total": float(refunds),
        "payouts_paid": float(payouts_paid),
        "payouts_pending": float(payouts_pending),
        # Outstanding liability: net earned by sellers but not yet paid out
        "outstanding_liability": float(Decimal(str(seller_net_pending))),
    }

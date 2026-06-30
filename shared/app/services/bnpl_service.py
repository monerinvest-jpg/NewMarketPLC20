"""
BNPL / pay-in-parts ("Сплит"). Provider-agnostic, mock-capable (same philosophy
as the payment/delivery gateways): works out of the box without a real provider.

Model: the BNPL provider settles the marketplace UPFRONT (so the order is paid
immediately), then collects from the buyer in N equal parts on a fixed interval.
We persist the schedule on InstallmentPlan for display; a real provider
integration would replace approve() with its API call.
"""
import json
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import InstallmentPlan, Order, utcnow
from app.services.settings_service import get_setting


async def config(db: AsyncSession) -> dict:
    async def _s(k, d):
        v = await get_setting(db, k)
        return v if v not in (None, "") else d
    return {
        "enabled": (await _s("bnpl_enabled", "true")).lower() == "true",
        "provider": await _s("bnpl_provider_name", "Сплит"),
        "parts": max(2, int(await _s("bnpl_parts", "4"))),
        "interval_days": int(await _s("bnpl_interval_days", "14")),
        "min_order": Decimal(await _s("bnpl_min_order", "3000")),
    }


def is_eligible(total: Decimal, cfg: dict) -> bool:
    return cfg["enabled"] and total >= cfg["min_order"]


def build_schedule(total: Decimal, parts: int, interval_days: int) -> tuple[Decimal, list[dict]]:
    """Split `total` into `parts` equal payments (last part absorbs rounding),
    first due today, the rest every `interval_days`. Returns (part_amount, schedule)."""
    part = (total / parts).quantize(Decimal("0.01"))
    schedule = []
    now = utcnow()
    accumulated = Decimal("0.00")
    for i in range(parts):
        amount = part if i < parts - 1 else (total - accumulated).quantize(Decimal("0.01"))
        accumulated += amount
        due = now + timedelta(days=interval_days * i)
        schedule.append({"due_date": due.date().isoformat(), "amount": str(amount)})
    return part, schedule


async def create_for_order(db: AsyncSession, order: Order, cfg: dict) -> InstallmentPlan:
    part_amount, schedule = build_schedule(order.total_price, cfg["parts"], cfg["interval_days"])
    plan = InstallmentPlan(
        order_id=order.id, provider=cfg["provider"], total=order.total_price,
        parts=cfg["parts"], part_amount=part_amount, schedule=json.dumps(schedule),
        status="active",
    )
    db.add(plan)
    await db.flush()
    return plan

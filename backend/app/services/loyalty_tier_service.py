"""
Tiered loyalty program.

A buyer accumulates `qualifying_spend` from completed orders. Their tier is the
highest active LoyaltyTier whose `min_spend` ≤ qualifying_spend. Tiers are
admin-configurable (threshold, cashback %, perks, free shipping, retention).
Inactivity decay: if no qualifying purchase within the tier's `retention_days`,
the buyer drops one level (handled by `decay_sweep`, run daily).
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import LoyaltyTier, NotificationType, Order, User
from app.services.notification_service import notify

DEFAULT_TIERS = [
    {"key": "bronze", "name": "Бронза", "level": 1, "min_spend": Decimal("0"),
     "cashback_percent": Decimal("2.00"), "free_shipping": False, "retention_days": 0,
     "color": "#cd7f32", "perks": "Базовый кэшбэк 2%"},
    {"key": "silver", "name": "Серебро", "level": 2, "min_spend": Decimal("30000"),
     "cashback_percent": Decimal("4.00"), "free_shipping": False, "retention_days": 180,
     "color": "#9ca3af", "perks": "Кэшбэк 4%, ранний доступ к распродажам"},
    {"key": "gold", "name": "Золото", "level": 3, "min_spend": Decimal("100000"),
     "cashback_percent": Decimal("7.00"), "free_shipping": True, "retention_days": 120,
     "color": "#f59e0b", "perks": "Кэшбэк 7%, бесплатная доставка, приоритетная поддержка"},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_default_tiers(db: AsyncSession) -> int:
    created = 0
    for t in DEFAULT_TIERS:
        exists = (await db.execute(select(LoyaltyTier).where(LoyaltyTier.key == t["key"]))).scalar_one_or_none()
        if not exists:
            db.add(LoyaltyTier(**t, is_active=True))
            created += 1
    return created


async def _active_tiers(db: AsyncSession) -> list[LoyaltyTier]:
    rows = (await db.execute(
        select(LoyaltyTier).where(LoyaltyTier.is_active == True).order_by(LoyaltyTier.level.asc())  # noqa: E712
    )).scalars().all()
    return list(rows)


async def tier_for_spend(db: AsyncSession, spend: Decimal) -> Optional[LoyaltyTier]:
    """Highest active tier the spend qualifies for."""
    tiers = await _active_tiers(db)
    qualified = [t for t in tiers if t.min_spend <= spend]
    return max(qualified, key=lambda t: t.level) if qualified else (tiers[0] if tiers else None)


async def get_tier(db: AsyncSession, tier_id: Optional[int]) -> Optional[LoyaltyTier]:
    if tier_id is None:
        return None
    return (await db.execute(select(LoyaltyTier).where(LoyaltyTier.id == tier_id))).scalar_one_or_none()


async def recompute_tier(db: AsyncSession, user: User, notify_upgrade: bool = True) -> Optional[LoyaltyTier]:
    """Set the user's tier from their qualifying spend; notify on upgrade."""
    new_tier = await tier_for_spend(db, user.qualifying_spend or Decimal("0"))
    old_tier_id = user.loyalty_tier_id
    if new_tier and new_tier.id != old_tier_id:
        old = await get_tier(db, old_tier_id)
        user.loyalty_tier_id = new_tier.id
        user.tier_since = _now()
        if notify_upgrade and (old is None or new_tier.level > old.level):
            await notify(
                db, user.id, NotificationType.system,
                title=f"Новый уровень лояльности: {new_tier.name}",
                body=f"Кэшбэк теперь {new_tier.cashback_percent}%.",
                link="/loyalty",
            )
    return new_tier


async def on_order_completed(db: AsyncSession, order: Order) -> Optional[LoyaltyTier]:
    """Accumulate qualifying spend from a completed order and refresh the tier."""
    buyer = (await db.execute(select(User).where(User.id == order.buyer_id))).scalar_one_or_none()
    if not buyer:
        return None
    buyer.qualifying_spend = (buyer.qualifying_spend or Decimal("0")) + (order.subtotal or Decimal("0"))
    buyer.last_qualifying_order_at = _now()
    return await recompute_tier(db, buyer)


async def cashback_percent_for(db: AsyncSession, user: User, fallback: Decimal) -> Decimal:
    """The buyer's effective cashback rate: tier rate if set, else the flat default."""
    tier = await get_tier(db, user.loyalty_tier_id)
    return tier.cashback_percent if tier else fallback


async def has_free_shipping(db: AsyncSession, user: User) -> bool:
    tier = await get_tier(db, user.loyalty_tier_id)
    return bool(tier and tier.free_shipping)


async def decay_sweep(db: AsyncSession) -> dict:
    """Drop a tier for buyers inactive beyond their tier's retention window."""
    tiers = await _active_tiers(db)
    by_level = sorted(tiers, key=lambda t: t.level)
    downgraded = 0
    now = _now()
    # Only consider users currently on a tier with a retention limit.
    users = (await db.execute(
        select(User).where(User.loyalty_tier_id.is_not(None))
    )).scalars().all()
    for user in users:
        tier = next((t for t in tiers if t.id == user.loyalty_tier_id), None)
        if not tier or tier.retention_days <= 0 or tier.level <= 1:
            continue
        last = user.last_qualifying_order_at or user.tier_since
        if last is None:
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last + timedelta(days=tier.retention_days) < now:
            # Drop to the previous level and cap qualifying spend at its threshold.
            lower = max((t for t in by_level if t.level < tier.level), key=lambda t: t.level, default=None)
            if lower:
                user.loyalty_tier_id = lower.id
                user.qualifying_spend = lower.min_spend
                user.tier_since = now
                user.last_qualifying_order_at = now
                downgraded += 1
                await notify(
                    db, user.id, NotificationType.system,
                    title=f"Уровень понижен до «{lower.name}»",
                    body="Из-за отсутствия покупок. Совершите заказ, чтобы вернуть уровень.",
                    link="/loyalty",
                )
    return {"downgraded": downgraded}


async def user_status(db: AsyncSession, user: User) -> dict:
    """Current tier, next tier, progress, and time-to-downgrade for the buyer UI."""
    tiers = await _active_tiers(db)
    if user.loyalty_tier_id is None:
        await recompute_tier(db, user, notify_upgrade=False)
    current = await get_tier(db, user.loyalty_tier_id)
    spend = user.qualifying_spend or Decimal("0")

    higher = sorted([t for t in tiers if current and t.level > current.level], key=lambda t: t.level)
    next_tier = higher[0] if higher else None
    to_next = (next_tier.min_spend - spend) if next_tier else Decimal("0")

    downgrade_at = None
    days_to_downgrade = None
    if current and current.retention_days > 0 and current.level > 1:
        last = user.last_qualifying_order_at or user.tier_since
        if last:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            downgrade_dt = last + timedelta(days=current.retention_days)
            downgrade_at = downgrade_dt.isoformat()
            days_to_downgrade = max(0, (downgrade_dt - _now()).days)

    return {
        "qualifying_spend": str(spend),
        "current": _tier_dict(current),
        "next": _tier_dict(next_tier),
        "to_next_amount": str(max(Decimal("0"), to_next)),
        "downgrade_at": downgrade_at,
        "days_to_downgrade": days_to_downgrade,
        "all_tiers": [_tier_dict(t) for t in sorted(tiers, key=lambda x: x.level)],
    }


def _tier_dict(t: Optional[LoyaltyTier]) -> Optional[dict]:
    if not t:
        return None
    return {
        "id": t.id, "key": t.key, "name": t.name, "level": t.level,
        "min_spend": str(t.min_spend), "cashback_percent": str(t.cashback_percent),
        "free_shipping": t.free_shipping, "perks": t.perks, "color": t.color,
        "retention_days": t.retention_days,
    }

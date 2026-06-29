"""
Seller trust: KYC verification + trust badges (Проверенный / VIP).

Badge rules (all thresholds admin-tunable in settings):
  * VIP  — paid (vip_until in the future) OR earned by reputation
           (rating ≥ vip_auto_rating_min AND reviews_count ≥ vip_auto_reviews_min);
  * Проверенный — KYC documents approved (shop.kyc_verified).
VIP outranks Проверенный.
"""
import json
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Shop, SellerVerification, SellerVerificationStatus, User,
    Transaction, TransactionType, utcnow,
)
from app.services.settings_service import get_setting


async def trust_config(db: AsyncSession) -> dict:
    async def _s(k, d):
        v = await get_setting(db, k)
        return v if v not in (None, "") else d
    return {
        "enabled": (await _s("trust_badges_enabled", "true")).lower() == "true",
        "vip_price": Decimal(await _s("vip_price", "990")),
        "vip_days": int(await _s("vip_duration_days", "30")),
        "rating_min": Decimal(await _s("vip_auto_rating_min", "4.8")),
        "reviews_min": int(await _s("vip_auto_reviews_min", "50")),
        "kyc_required_for_payout": (await _s("kyc_required_for_payout", "false")).lower() == "true",
    }


def compute_badge(shop: Shop, cfg: dict) -> Optional[str]:
    if not cfg["enabled"]:
        return None
    now = utcnow()
    vip_paid = shop.vip_until is not None and shop.vip_until > now
    vip_rep = (shop.rating or Decimal("0")) >= cfg["rating_min"] and (shop.reviews_count or 0) >= cfg["reviews_min"]
    if vip_paid or vip_rep:
        return "vip"
    if shop.kyc_verified:
        return "verified"
    return None


async def badge_for_shop_id(db: AsyncSession, shop_id: int) -> Optional[str]:
    shop = (await db.execute(select(Shop).where(Shop.id == shop_id))).scalar_one_or_none()
    if not shop:
        return None
    return compute_badge(shop, await trust_config(db))


async def buy_vip(db: AsyncSession, user: User, shop: Shop) -> Shop:
    """Charge the owner's balance and extend VIP. Raises ValueError if short."""
    cfg = await trust_config(db)
    price = cfg["vip_price"]
    if (user.balance or Decimal("0")) < price:
        raise ValueError(f"Недостаточно средств на балансе (нужно {price} ₽)")
    user.balance = (user.balance - price).quantize(Decimal("0.01"))
    base = shop.vip_until if (shop.vip_until and shop.vip_until > utcnow()) else utcnow()
    shop.vip_until = base + timedelta(days=cfg["vip_days"])
    db.add(Transaction(
        user_id=user.id, type=TransactionType.payout, amount=-price,
        description=f"Покупка VIP-статуса магазина на {cfg['vip_days']} дн.",
        balance_after=user.balance,
    ))
    await db.flush()
    return shop


async def submit_kyc(db: AsyncSession, shop_id: int, document_keys: list[str], note: str = "") -> SellerVerification:
    rec = (await db.execute(
        select(SellerVerification).where(SellerVerification.shop_id == shop_id)
    )).scalar_one_or_none()
    if rec and rec.status == SellerVerificationStatus.verified:
        return rec
    if not rec:
        rec = SellerVerification(shop_id=shop_id)
        db.add(rec)
    rec.document_keys = json.dumps(document_keys)
    rec.note = note
    rec.status = SellerVerificationStatus.pending
    rec.submitted_at = utcnow()
    rec.reason = None
    await db.flush()
    return rec


async def review_kyc(db: AsyncSession, shop_id: int, approve: bool, reviewer_id: int, reason: str = "") -> SellerVerification:
    rec = (await db.execute(
        select(SellerVerification).where(SellerVerification.shop_id == shop_id)
    )).scalar_one_or_none()
    if not rec:
        raise ValueError("Заявка на верификацию не найдена")
    rec.reviewed_by_id = reviewer_id
    rec.reviewed_at = utcnow()
    if approve:
        rec.status = SellerVerificationStatus.verified
        shop = (await db.execute(select(Shop).where(Shop.id == shop_id))).scalar_one_or_none()
        if shop:
            shop.kyc_verified = True
    else:
        rec.status = SellerVerificationStatus.rejected
        rec.reason = reason
    await db.flush()
    return rec

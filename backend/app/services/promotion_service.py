"""
Paid promotion & homepage auction.

Two monetization shapes share one model:
- fixed-price features (e.g. highlight a product card): charged up-front for a
  period, immediately active;
- auction features (the homepage first row): sellers place a *daily* bid; a
  settlement pass ranks bids and the top `slots` win — they are shown and
  charged for the day, the rest are marked `outbid`.

All charges debit the shop owner's balance (BalanceTransaction + Transaction),
mirroring how payouts/refunds move money elsewhere.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    AdWalletTransaction, BalanceTransaction, BalanceTransactionType, NotificationType,
    Order, OrderItem, OrderStatus, PaidFeature, PaidFeaturePricing, Product, ProductStatus,
    Promotion, PromotionStatus, Shop, Transaction, TransactionType, User,
)

# Orders that count as real revenue for ad attribution.
_REVENUE_STATUSES = (
    OrderStatus.paid, OrderStatus.processing, OrderStatus.shipped,
    OrderStatus.delivered, OrderStatus.completed,
)

# Default catalog created on first seed; admins edit price/slots/toggle later.
DEFAULT_FEATURES = [
    {
        "key": "homepage_top", "name": "Продвижение на главной (первый ряд)",
        "description": "Карточка товара в первом ряду главной страницы. Аукцион: побеждают "
                       "ставки с наибольшей дневной ценой.",
        "placement": "homepage", "pricing_mode": PaidFeaturePricing.auction,
        "price": Decimal("199.00"), "billing_period": "day", "slots": 5, "is_enabled": True,
    },
    {
        "key": "category_top", "name": "Топ категории",
        "description": "Поднятие товара в начало выдачи категории.",
        "placement": "category", "pricing_mode": PaidFeaturePricing.auction,
        "price": Decimal("99.00"), "billing_period": "day", "slots": 3, "is_enabled": True,
    },
    {
        "key": "product_highlight", "name": "Выделение карточки",
        "description": "Цветная рамка и бейдж на карточке товара на 7 дней.",
        "placement": "product_card", "pricing_mode": PaidFeaturePricing.fixed,
        "price": Decimal("499.00"), "billing_period": "week", "slots": 0, "is_enabled": True,
    },
]


# Top-up packages for the advertising wallet. Larger packages add a bonus.
AD_PACKAGES = [
    {"id": "ad_1000", "amount": Decimal("1000.00"), "bonus": Decimal("0.00")},
    {"id": "ad_3000", "amount": Decimal("3000.00"), "bonus": Decimal("300.00")},
    {"id": "ad_5000", "amount": Decimal("5000.00"), "bonus": Decimal("750.00")},
    {"id": "ad_10000", "amount": Decimal("10000.00"), "bonus": Decimal("2000.00")},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_today() -> datetime:
    return _now().replace(hour=0, minute=0, second=0, microsecond=0)


def _period_end(billing_period: str) -> Optional[datetime]:
    if billing_period == "week":
        return _now() + timedelta(days=7)
    if billing_period == "day":
        return _now() + timedelta(days=1)
    return None  # "once" — no expiry


async def ensure_default_features(db: AsyncSession) -> int:
    """Seed the catalog with the default features if missing (idempotent)."""
    created = 0
    for f in DEFAULT_FEATURES:
        exists = (await db.execute(
            select(PaidFeature).where(PaidFeature.key == f["key"])
        )).scalar_one_or_none()
        if not exists:
            db.add(PaidFeature(**f))
            created += 1
    return created


async def topup_wallet(db: AsyncSession, shop: Shop, package_id: str) -> dict:
    """
    Credit the shop's advertising wallet from a package. Funds come from the
    shop owner's main balance (a transfer), plus any package bonus. The ad wallet
    is what promotion charges draw from.
    """
    pkg = next((p for p in AD_PACKAGES if p["id"] == package_id), None)
    if pkg is None:
        raise ValueError("Неизвестный пакет пополнения")

    owner = (await db.execute(select(User).where(User.id == shop.owner_id))).scalar_one_or_none()
    if owner is None or owner.balance < pkg["amount"]:
        raise ValueError("Недостаточно средств на основном балансе для пополнения")

    # Move money: debit owner main balance, credit ad wallet (+ bonus).
    owner.balance -= pkg["amount"]
    db.add(BalanceTransaction(
        user_id=owner.id, change=-pkg["amount"], type=BalanceTransactionType.debit,
        reference_type="ad_wallet", description="Пополнение рекламного кошелька",
        balance_after=owner.balance,
    ))
    shop.ad_balance = (shop.ad_balance or Decimal("0.00")) + pkg["amount"]
    db.add(AdWalletTransaction(
        shop_id=shop.id, change=pkg["amount"], kind="topup",
        description=f"Пополнение ({package_id})", balance_after=shop.ad_balance,
    ))
    if pkg["bonus"] > 0:
        shop.ad_balance += pkg["bonus"]
        db.add(AdWalletTransaction(
            shop_id=shop.id, change=pkg["bonus"], kind="bonus",
            description="Бонус пакета", balance_after=shop.ad_balance,
        ))
    await db.flush()
    return {"ad_balance": str(shop.ad_balance), "credited": str(pkg["amount"] + pkg["bonus"])}


async def _charge_shop(db: AsyncSession, shop: Shop, amount: Decimal, description: str) -> bool:
    """Debit the shop's advertising wallet. Returns False on insufficient funds."""
    if (shop.ad_balance or Decimal("0.00")) < amount:
        return False
    shop.ad_balance -= amount
    db.add(AdWalletTransaction(
        shop_id=shop.id, change=-amount, kind="spend",
        description=description, balance_after=shop.ad_balance,
    ))
    return True


async def place_promotion(
    db: AsyncSession, shop: Shop, feature: PaidFeature,
    bid_amount: Decimal, product_id: Optional[int] = None,
) -> Promotion:
    """
    Place an auction bid or buy a fixed-price feature. Fixed features are charged
    and activated immediately; auction features create a pending bid that the
    settlement pass evaluates. Raises ValueError on validation problems.
    """
    if not feature.is_enabled:
        raise ValueError("Эта возможность сейчас недоступна")
    if bid_amount < feature.price:
        raise ValueError(f"Минимальная ставка/цена — {feature.price} ₽")

    promo = Promotion(
        shop_id=shop.id, product_id=product_id, feature_id=feature.id,
        feature_key=feature.key, placement=feature.placement, bid_amount=bid_amount,
    )

    if feature.pricing_mode == PaidFeaturePricing.fixed:
        if not await _charge_shop(db, shop, bid_amount, f"Покупка: {feature.name}"):
            raise ValueError("Недостаточно средств на рекламном кошельке. Пополните его.")
        promo.status = PromotionStatus.active
        promo.starts_at = _now()
        promo.ends_at = _period_end(feature.billing_period)
        promo.last_charged_at = _now()
        promo.total_spent = bid_amount
    else:
        # Auction: queue the bid; settlement decides winners and charges them.
        promo.status = PromotionStatus.pending

    db.add(promo)
    await db.flush()
    return promo


async def settle_auction(db: AsyncSession, feature: PaidFeature) -> dict:
    """
    Settle one auction feature: rank its non-terminal bids by amount, keep the
    top `slots` (charging each once per day), demote the rest to `outbid`.
    """
    candidates = (await db.execute(
        select(Promotion).where(
            Promotion.feature_id == feature.id,
            Promotion.status.in_([PromotionStatus.pending, PromotionStatus.active, PromotionStatus.outbid]),
        ).order_by(Promotion.bid_amount.desc(), Promotion.created_at.asc())
    )).scalars().all()

    winners, losers, charged = 0, 0, Decimal("0.00")
    today = _start_of_today()
    slot = 0
    for promo in candidates:
        if slot < feature.slots:
            # Charge once per calendar day for active placement.
            needs_charge = promo.last_charged_at is None or promo.last_charged_at < today
            if needs_charge:
                shop = (await db.execute(select(Shop).where(Shop.id == promo.shop_id))).scalar_one_or_none()
                ok = shop is not None and await _charge_shop(
                    db, shop, promo.bid_amount, f"Аукцион: {feature.name}"
                )
                if not ok:
                    # Out of funds — drop out of the auction.
                    promo.status = PromotionStatus.expired
                    losers += 1
                    continue
                promo.last_charged_at = _now()
                promo.total_spent = (promo.total_spent or Decimal("0.00")) + promo.bid_amount
                charged += promo.bid_amount
            promo.status = PromotionStatus.active
            if promo.starts_at is None:
                promo.starts_at = _now()
            winners += 1
            slot += 1
        else:
            if promo.status != PromotionStatus.expired:
                was_active = promo.status == PromotionStatus.active
                promo.status = PromotionStatus.outbid
                # Notify the seller only on the transition from active → outbid,
                # so we don't spam on every settlement pass.
                if was_active:
                    from app.services.notification_service import notify
                    shop = (await db.execute(select(Shop).where(Shop.id == promo.shop_id))).scalar_one_or_none()
                    if shop is not None:
                        await notify(
                            db, shop.owner_id, NotificationType.system,
                            title="Ставку перебили",
                            body=f"Ваша ставка в «{feature.name}» больше не в топе. "
                                 f"Повысьте ставку, чтобы вернуться.",
                            link="/seller/promotion",
                        )
            losers += 1

    return {"feature": feature.key, "winners": winners, "outbid": losers, "charged": str(charged)}


async def settle_all(db: AsyncSession) -> list[dict]:
    """Settle every enabled auction feature; expire ended fixed promotions."""
    # Expire fixed-price promotions whose period has elapsed.
    expired = (await db.execute(
        select(Promotion).where(
            Promotion.status == PromotionStatus.active,
            Promotion.ends_at.is_not(None),
            Promotion.ends_at < _now(),
        )
    )).scalars().all()
    for p in expired:
        p.status = PromotionStatus.expired

    features = (await db.execute(
        select(PaidFeature).where(
            PaidFeature.pricing_mode == PaidFeaturePricing.auction,
            PaidFeature.is_enabled == True,  # noqa: E712
        )
    )).scalars().all()
    results = [await settle_auction(db, f) for f in features]
    return results


async def active_homepage_products(db: AsyncSession, limit: int = 5) -> list[Product]:
    """Products currently winning the homepage auction (for the promoted row)."""
    pairs = await active_homepage_promotions(db, limit)
    return [p for _, p in pairs]


async def active_homepage_promotions(db: AsyncSession, limit: int = 5) -> list[tuple[Promotion, Product]]:
    """(promotion, product) pairs winning the homepage auction, ranked by bid."""
    rows = (await db.execute(
        select(Promotion)
        .where(
            Promotion.placement == "homepage",
            Promotion.status == PromotionStatus.active,
            Promotion.product_id.is_not(None),
        )
        .order_by(Promotion.bid_amount.desc())
        .limit(limit)
    )).scalars().all()
    if not rows:
        return []
    product_ids = [p.product_id for p in rows]
    prod_rows = (await db.execute(
        select(Product).options(selectinload(Product.images))
        .where(Product.id.in_(product_ids), Product.status == ProductStatus.active)
    )).scalars().all()
    by_id = {p.id: p for p in prod_rows}
    return [(promo, by_id[promo.product_id]) for promo in rows if promo.product_id in by_id]


async def record_event(db: AsyncSession, promotion_id: int, kind: str) -> bool:
    """Increment a promotion's impression/click counter (analytics)."""
    promo = (await db.execute(
        select(Promotion).where(Promotion.id == promotion_id)
    )).scalar_one_or_none()
    if not promo:
        return False
    if kind == "impression":
        promo.impressions = (promo.impressions or 0) + 1
    elif kind == "click":
        promo.clicks = (promo.clicks or 0) + 1
    else:
        return False
    return True


async def _attributed_revenue(db: AsyncSession, promo: Promotion) -> tuple[Decimal, int]:
    """Revenue and order count for the promoted product during the campaign
    (orders placed at/after the promotion started, in a paid+ state)."""
    if promo.product_id is None:
        return Decimal("0.00"), 0
    since = promo.starts_at or promo.created_at
    rows = (await db.execute(
        select(OrderItem.price_at_time, OrderItem.quantity, OrderItem.order_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            OrderItem.product_id == promo.product_id,
            OrderItem.shop_id == promo.shop_id,
            Order.created_at >= since,
            Order.status.in_(_REVENUE_STATUSES),
        )
    )).all()
    revenue = sum((r[0] * r[1] for r in rows), Decimal("0.00"))
    order_ids = {r[2] for r in rows}
    return Decimal(revenue).quantize(Decimal("0.01")), len(order_ids)


async def seller_analytics(db: AsyncSession, shop_id: int) -> dict:
    """Per-promotion ad metrics (impressions, clicks, CTR, spend, revenue, ROI)."""
    promos = (await db.execute(
        select(Promotion).where(Promotion.shop_id == shop_id)
        .order_by(Promotion.created_at.desc())
    )).scalars().all()

    rows = []
    tot_spent = tot_rev = Decimal("0.00")
    tot_impr = tot_clicks = tot_orders = 0
    for promo in promos:
        revenue, orders = await _attributed_revenue(db, promo)
        spent = promo.total_spent or Decimal("0.00")
        impressions = promo.impressions or 0
        clicks = promo.clicks or 0
        ctr = round(clicks / impressions * 100, 2) if impressions else 0.0
        cpc = (spent / clicks).quantize(Decimal("0.01")) if clicks else Decimal("0.00")
        roi = round(float((revenue - spent) / spent) * 100, 1) if spent > 0 else None

        prod = (await db.execute(
            select(Product.title).where(Product.id == promo.product_id)
        )).scalar_one_or_none() if promo.product_id else None

        rows.append({
            "promotion_id": promo.id, "product_id": promo.product_id, "product_title": prod,
            "feature_key": promo.feature_key, "placement": promo.placement,
            "status": promo.status.value, "bid_amount": str(promo.bid_amount),
            "impressions": impressions, "clicks": clicks, "ctr": ctr,
            "cpc": str(cpc), "spent": str(spent), "revenue": str(revenue),
            "orders": orders, "roi": roi,
        })
        tot_spent += spent
        tot_rev += revenue
        tot_impr += impressions
        tot_clicks += clicks
        tot_orders += orders

    return {
        "rows": rows,
        "totals": {
            "spent": str(tot_spent), "revenue": str(tot_rev),
            "impressions": tot_impr, "clicks": tot_clicks, "orders": tot_orders,
            "ctr": round(tot_clicks / tot_impr * 100, 2) if tot_impr else 0.0,
            "roi": round(float((tot_rev - tot_spent) / tot_spent) * 100, 1) if tot_spent > 0 else None,
        },
    }


async def auction_standing(db: AsyncSession, feature: PaidFeature) -> dict:
    """Current standing for a seller-facing auction view: minimum winning bid and
    total bidders, so a seller can size their bid."""
    bids = (await db.execute(
        select(Promotion.bid_amount).where(
            Promotion.feature_id == feature.id,
            Promotion.status.in_([PromotionStatus.pending, PromotionStatus.active]),
        ).order_by(Promotion.bid_amount.desc())
    )).all()
    amounts = [b[0] for b in bids]
    min_winning = amounts[feature.slots - 1] if len(amounts) >= feature.slots and feature.slots > 0 else feature.price
    return {
        "feature_key": feature.key, "slots": feature.slots,
        "bidders": len(amounts), "reserve": str(feature.price),
        "min_winning_bid": str(min_winning),
    }


async def wallet_overview(db: AsyncSession, shop: Shop, limit: int = 20) -> dict:
    """Ad-wallet balance, available top-up packages, and recent transactions."""
    rows = (await db.execute(
        select(AdWalletTransaction).where(AdWalletTransaction.shop_id == shop.id)
        .order_by(AdWalletTransaction.created_at.desc()).limit(limit)
    )).scalars().all()
    return {
        "ad_balance": str(shop.ad_balance or Decimal("0.00")),
        "packages": [
            {"id": p["id"], "amount": str(p["amount"]), "bonus": str(p["bonus"]),
             "total": str(p["amount"] + p["bonus"])}
            for p in AD_PACKAGES
        ],
        "transactions": [
            {"id": t.id, "change": str(t.change), "kind": t.kind,
             "description": t.description, "balance_after": str(t.balance_after),
             "created_at": t.created_at.isoformat()}
            for t in rows
        ],
    }

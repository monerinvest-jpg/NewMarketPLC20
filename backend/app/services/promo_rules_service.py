"""
Automatic cart-level promotions (no coupon code):
  - PromoRule (nplus / volume) — applied per matching line item;
  - Bundle — applied when all bundle items are present in the cart.

`compute_promotions` takes normalized cart lines and returns the total discount
plus a human-readable breakdown, used both for the cart summary preview and to
reduce the order subtotal at checkout.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Bundle, BundleItem, Product, PromoRule, PromoType


def _q(v: Decimal) -> Decimal:
    return Decimal(v).quantize(Decimal("0.01"))


def _rule_active(rule: PromoRule, now: datetime) -> bool:
    if not rule.is_active:
        return False
    if rule.starts_at and rule.starts_at > now:
        return False
    if rule.ends_at and rule.ends_at < now:
        return False
    return True


def _rule_matches(rule: PromoRule, product: Product) -> bool:
    if rule.product_id is not None:
        return product.id == rule.product_id
    if rule.category_id is not None:
        return product.category_id == rule.category_id
    return True  # whole-shop rule


def compute_nplus(rule: PromoRule, quantity: int, unit_price: Decimal) -> Decimal:
    """Buy `buy_quantity`, get `free_quantity` free — repeated per full group."""
    group = rule.buy_quantity + rule.free_quantity
    if group <= 0 or rule.free_quantity <= 0:
        return Decimal("0.00")
    free_units = (quantity // group) * rule.free_quantity
    return _q(unit_price * free_units)


def compute_volume(rule: PromoRule, quantity: int, unit_price: Decimal) -> Decimal:
    """Apply the best-qualifying quantity tier's percentage to the line total."""
    best_percent = Decimal("0")
    for tier in rule.tiers:
        try:
            min_qty = int(tier["min_qty"])
            percent = Decimal(str(tier["percent"]))
        except (KeyError, ValueError, TypeError):
            continue
        if quantity >= min_qty and percent > best_percent:
            best_percent = percent
    if best_percent <= 0:
        return Decimal("0.00")
    return _q(unit_price * quantity * best_percent / Decimal("100"))


async def _active_rules(db: AsyncSession, shop_ids: set[int], now: datetime) -> list[PromoRule]:
    if not shop_ids:
        return []
    rows = (await db.execute(
        select(PromoRule).where(PromoRule.shop_id.in_(shop_ids), PromoRule.is_active == True)  # noqa: E712
    )).scalars().all()
    return [r for r in rows if _rule_active(r, now)]


async def _active_bundles(db: AsyncSession, shop_ids: set[int]) -> list[Bundle]:
    if not shop_ids:
        return []
    rows = (await db.execute(
        select(Bundle).options(selectinload(Bundle.items))
        .where(Bundle.shop_id.in_(shop_ids), Bundle.is_active == True)  # noqa: E712
    )).scalars().all()
    return list(rows)


async def compute_promotions(db: AsyncSession, lines: list[dict]) -> dict:
    """
    lines: [{"product": Product, "quantity": int, "unit_price": Decimal}, ...]
    Returns {"discount": Decimal, "breakdown": [{"label", "amount"}]}.
    """
    now = datetime.now(timezone.utc)
    shop_ids = {ln["product"].shop_id for ln in lines}
    breakdown: list[dict] = []
    total = Decimal("0.00")

    # 1) Per-line rules (best single rule per line).
    rules = await _active_rules(db, shop_ids, now)
    for ln in lines:
        product, qty, price = ln["product"], ln["quantity"], ln["unit_price"]
        best, best_label = Decimal("0.00"), None
        for rule in rules:
            if rule.shop_id != product.shop_id or not _rule_matches(rule, product):
                continue
            if rule.type == PromoType.nplus:
                d = compute_nplus(rule, qty, price)
            else:
                d = compute_volume(rule, qty, price)
            if d > best:
                best, best_label = d, rule.title
        if best > 0:
            total += best
            breakdown.append({"label": best_label, "amount": str(best)})

    # 2) Bundles — apply when all items are present in sufficient quantity.
    qty_by_product = {ln["product"].id: ln["quantity"] for ln in lines}
    price_by_product = {ln["product"].id: ln["unit_price"] for ln in lines}
    bundles = await _active_bundles(db, shop_ids)
    for bundle in bundles:
        if not bundle.items:
            continue
        # How many full bundle sets does the cart contain?
        sets = None
        for bi in bundle.items:
            have = qty_by_product.get(bi.product_id, 0)
            need = bi.quantity or 1
            possible = have // need
            sets = possible if sets is None else min(sets, possible)
        if not sets:
            continue
        # Saving per set = sum(item list prices) − bundle_price (never negative).
        list_price = sum(
            (price_by_product.get(bi.product_id, Decimal("0.00")) * (bi.quantity or 1))
            for bi in bundle.items
        )
        saving_per_set = max(Decimal("0.00"), _q(Decimal(list_price) - bundle.bundle_price))
        saving = _q(saving_per_set * sets)
        if saving > 0:
            total += saving
            breakdown.append({"label": f"Набор «{bundle.title}»", "amount": str(saving)})

    return {"discount": _q(total), "breakdown": breakdown}


async def bundles_for_product(db: AsyncSession, product_id: int) -> list[dict]:
    """Active bundles that include the product, with computed list price & saving."""
    bundle_ids = (await db.execute(
        select(BundleItem.bundle_id).where(BundleItem.product_id == product_id)
    )).all()
    ids = [b[0] for b in bundle_ids]
    if not ids:
        return []
    bundles = (await db.execute(
        select(Bundle).options(selectinload(Bundle.items).selectinload(BundleItem.product))
        .where(Bundle.id.in_(ids), Bundle.is_active == True)  # noqa: E712
    )).scalars().all()

    result = []
    for b in bundles:
        items = []
        list_price = Decimal("0.00")
        for bi in b.items:
            if bi.product is None:
                continue
            line = bi.product.price * (bi.quantity or 1)
            list_price += line
            items.append({
                "product_id": bi.product_id, "title": bi.product.title,
                "quantity": bi.quantity, "price": str(bi.product.price),
            })
        result.append({
            "id": b.id, "title": b.title, "description": b.description,
            "bundle_price": str(b.bundle_price), "list_price": str(_q(list_price)),
            "saving": str(max(Decimal("0.00"), _q(list_price - b.bundle_price))),
            "items": items,
        })
    return result

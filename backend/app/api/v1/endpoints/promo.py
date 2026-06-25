"""
Advanced-promotion endpoints: seller CRUD for promo rules (nplus/volume) and
bundles, plus public reads (bundles for a product, active rules for a shop).
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_seller
from app.core.database import get_db
from app.models.models import Bundle, BundleItem, Product, PromoRule, Shop, User
from app.schemas.schemas import (
    BundleCreate, BundleOut, PromoRuleCreate, PromoRuleOut, PromoRuleUpdate,
)
from app.services import promo_rules_service

seller_router = APIRouter(prefix="/seller", tags=["promo"])
public_router = APIRouter(tags=["promo-public"])


async def _shop(db: AsyncSession, user: User) -> Shop:
    shop = (await db.execute(select(Shop).where(Shop.owner_id == user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    return shop


# ─── Promo rules ───────────────────────────────────────────────────────────────

@seller_router.get("/promo-rules", response_model=list[PromoRuleOut])
async def list_rules(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_seller)):
    shop = await _shop(db, user)
    rows = (await db.execute(
        select(PromoRule).where(PromoRule.shop_id == shop.id).order_by(PromoRule.created_at.desc())
    )).scalars().all()
    return list(rows)


@seller_router.post("/promo-rules", response_model=PromoRuleOut)
async def create_rule(
    payload: PromoRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_seller),
):
    shop = await _shop(db, user)
    rule = PromoRule(
        shop_id=shop.id, title=payload.title, type=payload.type, is_active=payload.is_active,
        starts_at=payload.starts_at, ends_at=payload.ends_at,
        product_id=payload.product_id, category_id=payload.category_id,
        buy_quantity=payload.buy_quantity, free_quantity=payload.free_quantity,
        tiers_json=json.dumps([t.model_dump(mode="json") for t in payload.tiers]) if payload.tiers else None,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@seller_router.patch("/promo-rules/{rule_id}", response_model=PromoRuleOut)
async def update_rule(
    rule_id: int,
    payload: PromoRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_seller),
):
    shop = await _shop(db, user)
    rule = (await db.execute(
        select(PromoRule).where(PromoRule.id == rule_id, PromoRule.shop_id == shop.id)
    )).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Акция не найдена")
    data = payload.model_dump(exclude_unset=True)
    tiers = data.pop("tiers", None)
    for k, v in data.items():
        setattr(rule, k, v)
    if tiers is not None:
        rule.tiers_json = json.dumps(tiers)
    await db.commit()
    await db.refresh(rule)
    return rule


@seller_router.delete("/promo-rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_seller)):
    shop = await _shop(db, user)
    rule = (await db.execute(
        select(PromoRule).where(PromoRule.id == rule_id, PromoRule.shop_id == shop.id)
    )).scalar_one_or_none()
    if rule:
        await db.delete(rule)
        await db.commit()


# ─── Bundles ───────────────────────────────────────────────────────────────────

@seller_router.get("/bundles", response_model=list[BundleOut])
async def list_bundles(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_seller)):
    shop = await _shop(db, user)
    rows = (await db.execute(
        select(Bundle).options(selectinload(Bundle.items))
        .where(Bundle.shop_id == shop.id).order_by(Bundle.created_at.desc())
    )).scalars().all()
    return list(rows)


@seller_router.post("/bundles", response_model=BundleOut)
async def create_bundle(
    payload: BundleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_seller),
):
    shop = await _shop(db, user)
    # All bundle products must belong to this shop.
    product_ids = [i.product_id for i in payload.items]
    owned = (await db.execute(
        select(Product.id).where(Product.id.in_(product_ids), Product.shop_id == shop.id)
    )).all()
    if len({p[0] for p in owned}) != len(set(product_ids)):
        raise HTTPException(status_code=400, detail="Все товары набора должны принадлежать вашему магазину")

    bundle = Bundle(
        shop_id=shop.id, title=payload.title, description=payload.description,
        bundle_price=payload.bundle_price, is_active=payload.is_active,
    )
    db.add(bundle)
    await db.flush()
    for i in payload.items:
        db.add(BundleItem(bundle_id=bundle.id, product_id=i.product_id, quantity=i.quantity))
    await db.commit()
    bundle = (await db.execute(
        select(Bundle).options(selectinload(Bundle.items)).where(Bundle.id == bundle.id)
    )).scalar_one()
    return bundle


@seller_router.patch("/bundles/{bundle_id}", response_model=BundleOut)
async def update_bundle(
    bundle_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_seller),
):
    shop = await _shop(db, user)
    bundle = (await db.execute(
        select(Bundle).options(selectinload(Bundle.items))
        .where(Bundle.id == bundle_id, Bundle.shop_id == shop.id)
    )).scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Набор не найден")
    for field in ("title", "description", "is_active"):
        if field in payload:
            setattr(bundle, field, payload[field])
    if "bundle_price" in payload:
        bundle.bundle_price = payload["bundle_price"]
    await db.commit()
    await db.refresh(bundle)
    return bundle


@seller_router.delete("/bundles/{bundle_id}", status_code=204)
async def delete_bundle(bundle_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_seller)):
    shop = await _shop(db, user)
    bundle = (await db.execute(
        select(Bundle).where(Bundle.id == bundle_id, Bundle.shop_id == shop.id)
    )).scalar_one_or_none()
    if bundle:
        await db.delete(bundle)
        await db.commit()


# ─── Public ────────────────────────────────────────────────────────────────────

@public_router.get("/products/{product_id}/bundles")
async def product_bundles(product_id: int, db: AsyncSession = Depends(get_db)):
    """Bundles that include this product, with list price and saving."""
    return await promo_rules_service.bundles_for_product(db, product_id)


@public_router.get("/shops/{shop_id}/promos", response_model=list[PromoRuleOut])
async def shop_promos(shop_id: int, db: AsyncSession = Depends(get_db)):
    """Active promo rules of a shop (for display on the shop page)."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    rows = (await db.execute(
        select(PromoRule).where(PromoRule.shop_id == shop_id, PromoRule.is_active == True)  # noqa: E712
    )).scalars().all()
    return [r for r in rows if promo_rules_service._rule_active(r, now)]

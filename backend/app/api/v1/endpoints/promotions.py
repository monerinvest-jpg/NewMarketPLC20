"""
Paid promotion endpoints.

- seller_router (/seller/promotions): place auction bids / buy fixed features,
  list own promotions, view auction standing.
- admin_router (/admin): manage the paid-feature catalog (price/slots/toggle),
  view all promotions, trigger settlement.
- public_router (/promotions): the homepage "promoted" row (auction winners).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_moderator_or_admin, get_current_seller
from app.core.database import get_db
from app.models.models import PaidFeature, Promotion, PromotionStatus, Shop, User
from app.schemas.schemas import (
    AuctionStanding, PaidFeatureOut, PaidFeatureUpdate, ProductListOut,
    PromotionCreate, PromotionOut,
)
from app.services import promotion_service

seller_router = APIRouter(prefix="/seller/promotions", tags=["promotions"])
admin_router = APIRouter(prefix="/admin", tags=["promotions-admin"])
public_router = APIRouter(prefix="/promotions", tags=["promotions-public"])


async def _shop_for(db: AsyncSession, user: User) -> Shop:
    shop = (await db.execute(select(Shop).where(Shop.owner_id == user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    return shop


# ─────────────────────────── Public ───────────────────────────

@public_router.get("/homepage")
async def homepage_promoted(db: AsyncSession = Depends(get_db)):
    """Products winning the homepage auction — the promoted first row.
    Each item carries its promotion_id so the client can report impressions/clicks."""
    pairs = await promotion_service.active_homepage_promotions(db, limit=5)
    return [
        {"promotion_id": promo.id, "product": ProductListOut.model_validate(product).model_dump(mode="json")}
        for promo, product in pairs
    ]


class _PromoEvent(BaseModel):
    type: str  # impression | click


@public_router.post("/{promotion_id}/event")
async def promotion_event(
    promotion_id: int,
    payload: _PromoEvent,
    db: AsyncSession = Depends(get_db),
):
    """Record an impression or click for a promoted item (ad analytics)."""
    ok = await promotion_service.record_event(db, promotion_id, payload.type)
    if ok:
        await db.commit()
    return {"ok": ok}


# ─────────────────────────── Seller ───────────────────────────

@seller_router.get("/wallet")
async def get_wallet(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Advertising wallet: balance, top-up packages, recent transactions."""
    shop = await _shop_for(db, current_user)
    return await promotion_service.wallet_overview(db, shop)


@seller_router.post("/wallet/topup")
async def topup_wallet(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Top up the advertising wallet from a package (funded from main balance)."""
    shop = await _shop_for(db, current_user)
    package_id = payload.get("package_id")
    if not package_id:
        raise HTTPException(status_code=400, detail="Не указан пакет")
    try:
        result = await promotion_service.topup_wallet(db, shop, package_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return result


@seller_router.get("/analytics")
async def promotions_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Ad analytics for the seller's promotions: impressions, clicks, CTR, spend,
    attributed revenue and ROI per campaign, plus totals."""
    shop = await _shop_for(db, current_user)
    return await promotion_service.seller_analytics(db, shop.id)


@seller_router.get("/features", response_model=list[PaidFeatureOut])
async def list_features(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_seller),
):
    rows = (await db.execute(
        select(PaidFeature).where(PaidFeature.is_enabled == True)  # noqa: E712
    )).scalars().all()
    return list(rows)


@seller_router.get("", response_model=list[PromotionOut])
async def my_promotions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _shop_for(db, current_user)
    rows = (await db.execute(
        select(Promotion).where(Promotion.shop_id == shop.id)
        .order_by(Promotion.created_at.desc())
    )).scalars().all()
    return list(rows)


@seller_router.get("/standing/{feature_key}", response_model=AuctionStanding)
async def feature_standing(
    feature_key: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_seller),
):
    feature = (await db.execute(
        select(PaidFeature).where(PaidFeature.key == feature_key)
    )).scalar_one_or_none()
    if not feature:
        raise HTTPException(status_code=404, detail="Возможность не найдена")
    return await promotion_service.auction_standing(db, feature)


@seller_router.post("", response_model=PromotionOut)
async def create_promotion(
    payload: PromotionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _shop_for(db, current_user)
    feature = (await db.execute(
        select(PaidFeature).where(PaidFeature.key == payload.feature_key)
    )).scalar_one_or_none()
    if not feature:
        raise HTTPException(status_code=404, detail="Возможность не найдена")

    # If a product is targeted, it must belong to the seller's shop.
    if payload.product_id is not None:
        from app.models.models import Product
        prod = (await db.execute(
            select(Product).where(Product.id == payload.product_id)
        )).scalar_one_or_none()
        if not prod or prod.shop_id != shop.id:
            raise HTTPException(status_code=403, detail="Товар не принадлежит вашему магазину")

    try:
        promo = await promotion_service.place_promotion(
            db, shop, feature, payload.bid_amount, payload.product_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Settle immediately so the seller sees their auction result right away.
    if feature.pricing_mode.value == "auction":
        await promotion_service.settle_auction(db, feature)
    await db.commit()
    await db.refresh(promo)
    return promo


@seller_router.post("/{promotion_id}/cancel", response_model=PromotionOut)
async def cancel_promotion(
    promotion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _shop_for(db, current_user)
    promo = (await db.execute(
        select(Promotion).where(Promotion.id == promotion_id)
    )).scalar_one_or_none()
    if not promo or promo.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Продвижение не найдено")
    promo.status = PromotionStatus.cancelled
    await db.commit()
    await db.refresh(promo)
    return promo


# ─────────────────────────── Admin ───────────────────────────

@admin_router.get("/paid-features", response_model=list[PaidFeatureOut])
async def admin_list_features(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    # Make sure defaults exist so the catalog is never empty.
    created = await promotion_service.ensure_default_features(db)
    if created:
        await db.commit()
    rows = (await db.execute(select(PaidFeature).order_by(PaidFeature.id))).scalars().all()
    return list(rows)


@admin_router.patch("/paid-features/{feature_id}", response_model=PaidFeatureOut)
async def admin_update_feature(
    feature_id: int,
    payload: PaidFeatureUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    feature = (await db.execute(
        select(PaidFeature).where(PaidFeature.id == feature_id)
    )).scalar_one_or_none()
    if not feature:
        raise HTTPException(status_code=404, detail="Возможность не найдена")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(feature, field, value)
    await db.commit()
    await db.refresh(feature)
    return feature


@admin_router.get("/promotions", response_model=dict)
async def admin_list_promotions(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    status_filter: str | None = None,
):
    query = select(Promotion).order_by(Promotion.bid_amount.desc())
    if status_filter:
        try:
            query = query.where(Promotion.status == PromotionStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail="Недопустимый статус")
    rows = (await db.execute(query.limit(200))).scalars().all()
    return {"items": [PromotionOut.model_validate(p).model_dump(mode="json") for p in rows]}


@admin_router.post("/promotions/settle")
async def admin_settle(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """Run auction settlement now (also runs nightly via Celery)."""
    results = await promotion_service.settle_all(db)
    await db.commit()
    return {"status": "ok", "results": results}

"""
Favorites, reports, delivery, categories, user profile endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.models import Category, Favorite, Product, Report, User
from app.schemas.schemas import (
    CategoryOut, DeliveryCalculateRequest, DeliveryCalculateResponse,
    DeliveryQuoteOut, DeliveryServiceOut, PickupPointOut,
    ProductListOut, ReportCreate, ReportOut, UserOut, UserUpdate,
)
from app.services.delivery_service import DELIVERY_SERVICES, get_delivery_gateway

# ─── Favorites ────────────────────────────────────────────────────────────────
favorites_router = APIRouter(prefix="/favorites", tags=["favorites"])


@favorites_router.get("", response_model=list[ProductListOut])
async def get_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Favorite)
        .options(selectinload(Favorite.product).selectinload(Product.images))
        .where(Favorite.user_id == current_user.id)
    )
    return [f.product for f in result.scalars().all()]


@favorites_router.post("/{product_id}", status_code=201)
async def add_favorite(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(Favorite).where(Favorite.user_id == current_user.id, Favorite.product_id == product_id)
    )
    if existing.scalar_one_or_none():
        return {"status": "already_added"}
    db.add(Favorite(user_id=current_user.id, product_id=product_id))
    await db.commit()
    return {"status": "added"}


@favorites_router.delete("/{product_id}", status_code=204)
async def remove_favorite(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Favorite).where(Favorite.user_id == current_user.id, Favorite.product_id == product_id)
    )
    fav = result.scalar_one_or_none()
    if fav:
        await db.delete(fav)
        await db.commit()


# ─── Reports ──────────────────────────────────────────────────────────────────
reports_router = APIRouter(prefix="/reports", tags=["reports"])


@reports_router.post("", response_model=ReportOut, status_code=201)
async def create_report(
    payload: ReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = Report(
        reporter_id=current_user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


# ─── Delivery ─────────────────────────────────────────────────────────────────
delivery_router = APIRouter(prefix="/delivery", tags=["delivery"])


@delivery_router.get("/services", response_model=list[DeliveryServiceOut])
async def list_delivery_services():
    """Returns all delivery services available on the platform."""
    return [DeliveryServiceOut(code=code, name=name) for code, name in DELIVERY_SERVICES.items()]


@delivery_router.post("/calculate", response_model=DeliveryCalculateResponse)
async def calculate_delivery(payload: DeliveryCalculateRequest):
    gw = get_delivery_gateway(payload.service)
    rate = await gw.calculate_rate(payload.city_from, payload.city_to, payload.weight_g)
    return DeliveryCalculateResponse(
        cost=rate.cost,
        estimated_days=rate.estimated_days,
        service=rate.service,
    )


@delivery_router.post("/quote-all", response_model=list[DeliveryQuoteOut])
async def quote_all_delivery(payload: DeliveryCalculateRequest):
    """
    Returns a price/time quote from every delivery service at once, so the
    buyer can compare СДЭК / Ozon / Яндекс / Почта России side by side.
    """
    import asyncio

    async def quote(code: str, name: str) -> DeliveryQuoteOut:
        gw = get_delivery_gateway(code)
        rate = await gw.calculate_rate(payload.city_from, payload.city_to, payload.weight_g)
        return DeliveryQuoteOut(code=code, name=name, cost=rate.cost, estimated_days=rate.estimated_days)

    quotes = await asyncio.gather(*[
        quote(code, name) for code, name in DELIVERY_SERVICES.items()
    ])
    return sorted(quotes, key=lambda q: q.cost)


@delivery_router.get("/pickup-points", response_model=list[PickupPointOut])
async def list_pickup_points(city: str, service: str = "cdek"):
    """Returns pickup points (ПВЗ) for the given city and delivery service."""
    gw = get_delivery_gateway(service)
    points = await gw.get_pickup_points(city)
    return [PickupPointOut(**vars(p)) for p in points]


# ─── Categories (public) ──────────────────────────────────────────────────────
categories_router = APIRouter(prefix="/categories", tags=["categories"])


@categories_router.get("", response_model=list[CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Category)
        .options(selectinload(Category.children))
        .where(Category.parent_id == None)  # noqa: E711
        .order_by(Category.sort_order)
    )
    return result.scalars().all()


@categories_router.get("/{slug}", response_model=CategoryOut)
async def get_category(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Category)
        .options(selectinload(Category.children))
        .where(Category.slug == slug)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


# ─── User profile ─────────────────────────────────────────────────────────────
users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("/me", response_model=UserOut)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@users_router.patch("/me", response_model=UserOut)
async def update_profile(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.security import get_password_hash
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "password":
            current_user.password_hash = get_password_hash(value)
        else:
            setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@users_router.get("/me/referral-stats")
async def get_referral_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func
    from app.models.models import Referral
    from app.services.referral_service import ensure_referral_code

    code = await ensure_referral_code(current_user, db)
    await db.commit()

    total_referred = (
        await db.execute(
            select(func.count(Referral.id)).where(Referral.referrer_id == current_user.id)
        )
    ).scalar_one()

    paid_rewards = (
        await db.execute(
            select(func.count(Referral.id)).where(
                Referral.referrer_id == current_user.id,
                Referral.reward_paid == True,  # noqa: E712
            )
        )
    ).scalar_one()

    return {
        "referral_code": code,
        "referral_link": f"https://marketplace.com/register?ref={code}",
        "total_referred": total_referred,
        "paid_rewards": paid_rewards,
        "bonus_balance": current_user.bonus_balance,
        "balance": current_user.balance,
    }


@users_router.get("/me/balance-history")
async def get_balance_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.models import BalanceTransaction
    result = await db.execute(
        select(BalanceTransaction)
        .where(BalanceTransaction.user_id == current_user.id)
        .order_by(BalanceTransaction.created_at.desc())
        .limit(50)
    )
    from app.schemas.schemas import BalanceTransactionOut
    return [BalanceTransactionOut.model_validate(tx) for tx in result.scalars().all()]


# ─── Homepage banners (public) & recommendations ────────────────────────────────

home_router = APIRouter(prefix="/home", tags=["home"])


@home_router.get("/banners")
async def public_banners(db: AsyncSession = Depends(get_db)):
    from app.models.models import HomepageBanner
    from app.schemas.schemas import HomepageBannerOut
    result = await db.execute(
        select(HomepageBanner)
        .where(HomepageBanner.is_active == True)  # noqa: E712
        .order_by(HomepageBanner.sort_order)
    )
    return [HomepageBannerOut.model_validate(b) for b in result.scalars().all()]


products_extra_router = APIRouter(prefix="/products", tags=["products-extra"])


@products_extra_router.get("/{product_id}/recommendations")
async def product_recommendations(product_id: int, db: AsyncSession = Depends(get_db)):
    """
    "Bought together" recommendations: products most frequently purchased in the
    same orders as this one (from the materialized co-purchase signal), with a
    same-category fallback. Results are ordered by relevance.
    """
    from app.schemas.schemas import ProductListOut
    from app.services import recommendation_service

    products = await recommendation_service.get_product_recommendations(db, product_id, limit=8)
    return [ProductListOut.model_validate(p) for p in products]


recommendations_router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@recommendations_router.get("/for-me")
async def recommendations_for_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Personalized recommendations based on the user's purchase history."""
    from app.schemas.schemas import ProductListOut
    from app.services import recommendation_service

    products = await recommendation_service.recommended_for_user(db, current_user.id, limit=12)
    return [ProductListOut.model_validate(p) for p in products]


class _CartRecsRequest(BaseModel):
    product_ids: list[int]


@recommendations_router.post("/cart")
async def recommendations_for_cart(
    payload: _CartRecsRequest,
    db: AsyncSession = Depends(get_db),
):
    """"Frequently bought with your cart" — co-purchase across cart contents."""
    from app.schemas.schemas import ProductListOut
    from app.services import recommendation_service

    products = await recommendation_service.cart_recommendations(db, payload.product_ids[:50], limit=8)
    return [ProductListOut.model_validate(p) for p in products]



# ─── Currencies (item 11) ────────────────────────────────────────────────────────

currency_router = APIRouter(prefix="/currencies", tags=["currencies"])


@currency_router.get("")
async def list_currencies(db: AsyncSession = Depends(get_db)):
    """Public: available display currencies and their rates from base RUB."""
    from app.services.currency_service import get_rates
    rates = await get_rates(db)
    return [
        {"code": code, "rate": str(info["rate"]), "symbol": info["symbol"]}
        for code, info in rates.items()
    ]


# ─── SEO: sitemap & catalog facets (items 10, 5) ─────────────────────────────────

seo_router = APIRouter(tags=["seo"])


@seo_router.get("/sitemap.xml")
async def sitemap(db: AsyncSession = Depends(get_db)):
    """Generate a basic sitemap of active products and categories."""
    from fastapi.responses import Response
    from app.models.models import Product, Category, ProductStatus

    products = (await db.execute(
        select(Product.id, Product.slug, Product.updated_at)
        .where(Product.status == ProductStatus.active).limit(5000)
    )).all()
    categories = (await db.execute(select(Category.slug))).all()

    urls = []
    for cid, slug, updated in products:
        loc = f"/products/{slug or cid}"
        urls.append(f"<url><loc>{loc}</loc><changefreq>weekly</changefreq></url>")
    for (cslug,) in categories:
        urls.append(f"<url><loc>/catalog?category={cslug}</loc><changefreq>daily</changefreq></url>")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(urls) + "</urlset>"
    )
    return Response(content=xml, media_type="application/xml")


@seo_router.get("/catalog/facets")
async def catalog_facets(category_id: int | None = None, db: AsyncSession = Depends(get_db)):
    """
    Return available attribute filters (facets) with their distinct values for
    the catalog UI. Optionally scoped to a category. Powers faceted filtering.
    """
    from app.models.models import Attribute, ProductAttributeValue, Product
    from sqlalchemy import distinct

    attrs = (await db.execute(
        select(Attribute).where(Attribute.is_filterable == True).order_by(Attribute.sort_order)  # noqa: E712
    )).scalars().all()

    facets = []
    for attr in attrs:
        q = select(distinct(ProductAttributeValue.value)).where(
            ProductAttributeValue.attribute_id == attr.id
        )
        if category_id:
            q = q.join(Product, Product.id == ProductAttributeValue.product_id).where(
                Product.category_id == category_id
            )
        values = [v for (v,) in (await db.execute(q.limit(50))).all()]
        if values:
            facets.append({"id": attr.id, "name": attr.name, "slug": attr.slug, "values": sorted(values)})
    return facets

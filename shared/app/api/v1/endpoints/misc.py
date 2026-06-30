"""
Favorites, reports, delivery, categories, user profile endpoints.
"""
from decimal import Decimal

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
async def list_delivery_services(db: AsyncSession = Depends(get_db)):
    """Returns the delivery services enabled by the admin."""
    from app.services.delivery_service import enabled_delivery_services
    services = await enabled_delivery_services(db)
    return [DeliveryServiceOut(code=code, name=name) for code, name in services.items()]


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
async def quote_all_delivery(payload: DeliveryCalculateRequest, db: AsyncSession = Depends(get_db)):
    """
    Returns a price/time quote from every ENABLED delivery service at once, so
    the buyer can compare СДЭК / Ozon / Яндекс / Почта России side by side.
    """
    import asyncio
    from app.services.delivery_service import enabled_delivery_services

    async def quote(code: str, name: str) -> DeliveryQuoteOut:
        gw = get_delivery_gateway(code)
        rate = await gw.calculate_rate(payload.city_from, payload.city_to, payload.weight_g)
        return DeliveryQuoteOut(code=code, name=name, cost=rate.cost, estimated_days=rate.estimated_days)

    services = await enabled_delivery_services(db)
    quotes = await asyncio.gather(*[quote(code, name) for code, name in services.items()])
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
    from app.services.cache_service import cache_get, cache_set
    cache_key = "categories:tree"
    cached_val = await cache_get(cache_key)
    if cached_val is not None:
        return cached_val
    result = await db.execute(
        select(Category)
        .options(selectinload(Category.children))
        .where(Category.parent_id == None)  # noqa: E711
        .order_by(Category.sort_order)
    )
    data = [CategoryOut.model_validate(c).model_dump(mode="json") for c in result.scalars().all()]
    await cache_set(cache_key, data, ttl=600)
    return data


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


@users_router.get("/public-config")
async def public_config(db: AsyncSession = Depends(get_db)):
    """Whitelisted public settings the storefront needs (no auth)."""
    from app.services.settings_service import get_setting
    return {"gift_wrap_price": await get_setting(db, "gift_wrap_price")}


@users_router.get("/unsubscribe")
async def unsubscribe_from_marketing(token: str, db: AsyncSession = Depends(get_db)):
    """One-click marketing unsubscribe (HMAC-signed token from campaign emails)."""
    from fastapi.responses import HTMLResponse
    from app.services.campaign_service import verify_unsub_token
    uid = verify_unsub_token(token)
    if uid:
        user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if user:
            user.marketing_opt_out = True
            await db.commit()
    html = (
        "<html><body style='font-family:sans-serif;text-align:center;padding:60px;background:#f7f1e8'>"
        "<h2 style='color:#7c4a21'>Вы отписались от рассылки</h2>"
        "<p>Больше мы не будем присылать вам маркетинговые письма.</p></body></html>"
    )
    return HTMLResponse(html)


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
        "referral_balance": current_user.referral_balance,
    }


class WithdrawalAccountIn(BaseModel):
    tax_regime: str          # self_employed | individual | company
    legal_name: str
    inn: str
    account_details: str


class ReferralWithdrawalCreate(BaseModel):
    amount: Decimal


@users_router.get("/me/withdrawal-account")
async def get_withdrawal_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Referral balance + the user's withdrawal (tax/bank) details, if set."""
    from app.models.models import WithdrawalAccount
    acc = (await db.execute(
        select(WithdrawalAccount).where(WithdrawalAccount.user_id == current_user.id)
    )).scalar_one_or_none()
    return {
        "referral_balance": current_user.referral_balance,
        "account": None if not acc else {
            "tax_regime": acc.tax_regime.value,
            "legal_name": acc.legal_name,
            "inn": acc.inn,
            "account_details": acc.account_details,
        },
    }


@users_router.put("/me/withdrawal-account")
async def set_withdrawal_account(
    payload: WithdrawalAccountIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.models import WithdrawalAccount, TaxRegime
    try:
        regime = TaxRegime(payload.tax_regime)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный налоговый статус")
    acc = (await db.execute(
        select(WithdrawalAccount).where(WithdrawalAccount.user_id == current_user.id)
    )).scalar_one_or_none()
    if not acc:
        acc = WithdrawalAccount(user_id=current_user.id, tax_regime=regime,
                                legal_name=payload.legal_name, inn=payload.inn,
                                account_details=payload.account_details)
        db.add(acc)
    else:
        acc.tax_regime = regime
        acc.legal_name = payload.legal_name
        acc.inn = payload.inn
        acc.account_details = payload.account_details
    await db.commit()
    return {"ok": True}


@users_router.get("/me/referral-withdrawals")
async def my_referral_withdrawals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.models import PayoutRequest, PayoutSource
    reqs = (await db.execute(
        select(PayoutRequest).where(
            PayoutRequest.user_id == current_user.id,
            PayoutRequest.source == PayoutSource.referral,
        ).order_by(PayoutRequest.created_at.desc())
    )).scalars().all()
    return [
        {"id": r.id, "amount": r.amount, "status": r.status.value,
         "created_at": r.created_at.isoformat(), "admin_comment": r.admin_comment}
        for r in reqs
    ]


@users_router.post("/me/referral-withdrawals", status_code=201)
async def request_referral_withdrawal(
    payload: ReferralWithdrawalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Withdraw referral earnings to the user's bank account. Requires a withdrawal
    account with a tax status (self-employed/ИП/ООО). The amount is validated and
    reserved against referral_balance; it is deducted when admin marks it paid.
    """
    from app.models.models import WithdrawalAccount, PayoutRequest, PayoutSource, PayoutRequestStatus

    acc = (await db.execute(
        select(WithdrawalAccount).where(WithdrawalAccount.user_id == current_user.id)
    )).scalar_one_or_none()
    if not acc:
        raise HTTPException(status_code=400, detail="Сначала укажите реквизиты и налоговый статус (самозанятый/ИП/ООО)")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть положительной")
    if payload.amount > current_user.referral_balance:
        raise HTTPException(status_code=400, detail=f"Сумма превышает реферальный баланс ({current_user.referral_balance} ₽)")

    pending = (await db.execute(
        select(PayoutRequest).where(
            PayoutRequest.user_id == current_user.id,
            PayoutRequest.source == PayoutSource.referral,
            PayoutRequest.status.in_([PayoutRequestStatus.pending, PayoutRequestStatus.approved]),
        )
    )).scalars().all()
    reserved = sum((p.amount for p in pending), Decimal("0"))
    if reserved + payload.amount > current_user.referral_balance:
        raise HTTPException(status_code=400, detail="С учётом уже запрошенных выводов сумма превышает баланс")

    details = f"{acc.tax_regime.value} • {acc.legal_name} • ИНН {acc.inn} • {acc.account_details}"
    req = PayoutRequest(
        user_id=current_user.id, amount=payload.amount, source=PayoutSource.referral,
        payout_details=details, status=PayoutRequestStatus.pending,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return {"id": req.id, "amount": req.amount, "status": req.status.value}


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

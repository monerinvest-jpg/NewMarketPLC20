"""
Aggregate all v1 routers.
"""
from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.products import router as products_router
from app.api.v1.endpoints.orders import router as orders_router
from app.api.v1.endpoints.shops import router as shops_router
from app.api.v1.endpoints.cart import router as cart_router
from app.api.v1.endpoints.reviews import router as reviews_router
from app.api.v1.endpoints.subscription import router as subscription_router
from app.api.v1.endpoints.catalog_extra import router as catalog_extra_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.seller_tools import router as seller_tools_router
from app.api.v1.endpoints.returns_orders import router as returns_orders_router
from app.api.v1.endpoints.support import router as support_router
from app.api.v1.endpoints.promo import (
    seller_router as promo_rules_seller_router,
    public_router as promo_rules_public_router,
)
from app.api.v1.endpoints.disputes import (
    router as disputes_router,
    seller_router as disputes_seller_router,
)
from app.api.v1.endpoints.gifts import (
    router as gifts_router,
    admin_router as gifts_admin_router,
)
from app.api.v1.endpoints.loyalty import (
    router as loyalty_router,
    admin_router as loyalty_admin_router,
)
from app.api.v1.endpoints.promotions import (
    seller_router as promo_seller_router,
    admin_router as promo_admin_router,
    public_router as promo_public_router,
)
from app.api.v1.endpoints.buyer_extra import router as buyer_extra_router
from app.api.v1.endpoints.seller_inventory import router as seller_inventory_router
from app.api.v1.endpoints.seller_extra import router as seller_extra_router
from app.api.v1.endpoints.twofa import router as twofa_router
from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.misc import (
    favorites_router,
    reports_router,
    delivery_router,
    categories_router,
    users_router,
    home_router,
    products_extra_router,
    recommendations_router,
    currency_router,
    seo_router,
)

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(products_router)
api_router.include_router(products_extra_router)
api_router.include_router(orders_router)
api_router.include_router(shops_router)
api_router.include_router(cart_router)
api_router.include_router(reviews_router)
api_router.include_router(subscription_router)
api_router.include_router(catalog_extra_router)
api_router.include_router(notifications_router)
api_router.include_router(seller_tools_router)
api_router.include_router(returns_orders_router)
api_router.include_router(support_router)
api_router.include_router(promo_rules_seller_router)
api_router.include_router(promo_rules_public_router)
api_router.include_router(disputes_router)
api_router.include_router(disputes_seller_router)
api_router.include_router(gifts_router)
api_router.include_router(gifts_admin_router)
api_router.include_router(loyalty_router)
api_router.include_router(loyalty_admin_router)
api_router.include_router(promo_seller_router)
api_router.include_router(promo_admin_router)
api_router.include_router(promo_public_router)
api_router.include_router(buyer_extra_router)
api_router.include_router(seller_inventory_router)
api_router.include_router(seller_extra_router)
api_router.include_router(twofa_router)
api_router.include_router(favorites_router)
api_router.include_router(reports_router)
api_router.include_router(delivery_router)
api_router.include_router(categories_router)
api_router.include_router(home_router)
api_router.include_router(recommendations_router)
api_router.include_router(currency_router)
api_router.include_router(seo_router)
api_router.include_router(admin_router)

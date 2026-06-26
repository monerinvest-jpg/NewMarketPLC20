"""Catalog service — products, shops, reviews, categories, recommendations, SEO.

Kong prefixes: /api/v1/products, /shops, /reviews, /categories, /catalog,
/home, /recommendations, /favorites, /sitemap.xml
"""
from app.service_factory import create_service_app

from app.api.v1.endpoints.products import router as products_router
from app.api.v1.endpoints.shops import router as shops_router
from app.api.v1.endpoints.reviews import router as reviews_router
from app.api.v1.endpoints.catalog_extra import router as catalog_extra_router
# Public promo reads keyed by product/shop (/products/{id}/bundles, /shops/{id}/promos)
# — kept in catalog so the /products and /shops prefixes route to one service.
from app.api.v1.endpoints.promo import public_router as promo_rules_public_router
from app.api.v1.endpoints.misc import (
    products_extra_router,
    categories_router,
    home_router,
    recommendations_router,
    favorites_router,
    seo_router,
)

app = create_service_app(
    "catalog",
    [
        products_router,
        products_extra_router,
        shops_router,
        reviews_router,
        catalog_extra_router,
        promo_rules_public_router,
        categories_router,
        home_router,
        recommendations_router,
        favorites_router,
        seo_router,
    ],
)

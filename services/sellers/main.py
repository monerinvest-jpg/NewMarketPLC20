"""Sellers service — seller tools, inventory, subscriptions/plans, promotions, promo rules.

Owns the whole `/seller/*` namespace (except `/seller/sub-orders`, which the orders
service serves as a seller-facing view of order fulfillment).

Kong prefixes: /api/v1/seller, /subscription, /promotions, /upload
"""
from app.service_factory import create_service_app

from app.api.v1.endpoints.seller_tools import router as seller_tools_router
from app.api.v1.endpoints.seller_inventory import router as seller_inventory_router
from app.api.v1.endpoints.seller_extra import router as seller_extra_router
from app.api.v1.endpoints.subscription import router as subscription_router
from app.api.v1.endpoints.promo import seller_router as promo_rules_seller_router
from app.api.v1.endpoints.promotions import (
    seller_router as promo_seller_router,
    public_router as promo_public_router,
)
# Seller-facing dispute actions live under /seller/disputes — kept here so the
# entire /seller/* prefix routes to one service (buyer disputes stay in orders).
from app.api.v1.endpoints.disputes import seller_router as disputes_seller_router
from app.api.v1.endpoints.academy import seller_router as academy_seller_router

app = create_service_app(
    "sellers",
    [
        seller_tools_router,
        seller_inventory_router,
        seller_extra_router,
        subscription_router,
        promo_rules_seller_router,
        promo_seller_router,
        promo_public_router,
        disputes_seller_router,
        academy_seller_router,
    ],
)

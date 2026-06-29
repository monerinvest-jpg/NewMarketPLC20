"""Orders service — cart, orders, sub-orders, returns, disputes (buyer), delivery, buyer profile.

Kong prefixes: /api/v1/cart, /orders, /sub-orders, /returns, /product-subscriptions,
/disputes, /addresses, /wishlists, /recently-viewed, /delivery, and the specific
/seller/sub-orders (seller view of order fulfillment).
"""
from app.service_factory import create_service_app

from app.api.v1.endpoints.cart import router as cart_router
from app.api.v1.endpoints.orders import router as orders_router
from app.api.v1.endpoints.returns_orders import router as returns_orders_router
from app.api.v1.endpoints.disputes import router as disputes_router
from app.api.v1.endpoints.buyer_extra import router as buyer_extra_router
from app.api.v1.endpoints.digital_library import router as library_router
from app.api.v1.endpoints.misc import delivery_router

app = create_service_app(
    "orders",
    [
        cart_router,
        orders_router,
        returns_orders_router,
        disputes_router,
        buyer_extra_router,
        library_router,
        delivery_router,
    ],
)

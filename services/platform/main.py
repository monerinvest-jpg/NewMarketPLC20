"""Platform service — notifications, support, gifts, loyalty, currency, reports, admin.

Kong prefixes: /api/v1/notifications, /support, /gifts, /loyalty, /currencies,
/reports, /admin
"""
from app.service_factory import create_service_app

from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.support import router as support_router
from app.api.v1.endpoints.gifts import (
    router as gifts_router,
    admin_router as gifts_admin_router,
)
from app.api.v1.endpoints.loyalty import (
    router as loyalty_router,
    admin_router as loyalty_admin_router,
)
from app.api.v1.endpoints.admin import router as admin_router
# Admin-side promotion moderation lives under /admin/* — kept in platform so the
# whole /admin/* prefix routes to one service.
from app.api.v1.endpoints.promotions import admin_router as promo_admin_router
from app.api.v1.endpoints.misc import (
    currency_router,
    reports_router,
)

app = create_service_app(
    "platform",
    [
        notifications_router,
        support_router,
        gifts_router,
        gifts_admin_router,
        loyalty_router,
        loyalty_admin_router,
        promo_admin_router,
        currency_router,
        reports_router,
        admin_router,
    ],
)

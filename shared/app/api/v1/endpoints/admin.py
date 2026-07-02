"""
Admin API hub.

The former 95KB monolith is split into domain routers (users, shops,
moderation, orders, catalog, finance, analytics, platform). This module keeps
the historical import path — `from app.api.v1.endpoints.admin import router` —
by aggregating them; every sub-router carries the same /admin prefix and
per-endpoint RBAC dependencies.
"""
from fastapi import APIRouter

from app.api.v1.endpoints.admin_analytics import router as _analytics
from app.api.v1.endpoints.admin_users import router as _users
from app.api.v1.endpoints.admin_shops import router as _shops
from app.api.v1.endpoints.admin_moderation import router as _moderation
from app.api.v1.endpoints.admin_orders import router as _orders
from app.api.v1.endpoints.admin_catalog import router as _catalog
from app.api.v1.endpoints.admin_finance import router as _finance
from app.api.v1.endpoints.admin_platform import router as _platform

router = APIRouter()
for _sub in (_analytics, _users, _shops, _moderation, _orders, _catalog, _finance, _platform):
    router.include_router(_sub)

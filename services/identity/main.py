"""Identity service — auth, users, 2FA/security.

Kong prefixes: /api/v1/auth, /api/v1/users, /api/v1/2fa, /api/v1/security
"""
from app.service_factory import create_service_app

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.twofa import router as twofa_router
from app.api.v1.endpoints.misc import users_router

app = create_service_app(
    "identity",
    [
        auth_router,
        users_router,
        twofa_router,
    ],
)

"""
Shared FastAPI application factory for the marketplace microservices.

Every service (identity, catalog, orders, sellers, platform) is an independently
deployable image that runs only its slice of the API. They all import this
factory and the shared `app` library, so middleware/CORS/rate-limiting/health are
configured identically and routers keep the exact same `/api/v1/...` paths they
had in the former monolith (Kong routes to a service by path prefix).
"""
import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.ratelimit import limiter
from app.models.models import Base  # noqa: F401 – ensure all models are registered


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Ensure upload directories exist (local storage fallback; prod uses S3).
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "products"), exist_ok=True)
    yield


def create_service_app(service_name: str, routers: list) -> FastAPI:
    """Build a configured FastAPI app that mounts `routers` under /api/v1."""
    app = FastAPI(
        title=f"{settings.PROJECT_NAME} — {service_name}",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=_lifespan,
    )

    # Rate limiting (slowapi) — routes opt in via @limiter.limit(...) decorators.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static file serving for uploads (local dev; prod serves these from S3).
    if os.path.isdir(settings.UPLOAD_DIR):
        app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

    # Mount this service's routers under the shared /api/v1 prefix.
    aggregate = APIRouter()
    for router in routers:
        aggregate.include_router(router)
    app.include_router(aggregate, prefix=settings.API_V1_STR)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": service_name}

    return app

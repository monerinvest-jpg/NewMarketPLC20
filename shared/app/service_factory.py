"""
Shared FastAPI application factory for the marketplace microservices.

Every service (identity, catalog, orders, sellers, platform) is an independently
deployable image that runs only its slice of the API. They all import this
factory and the shared `app` library, so middleware/CORS/rate-limiting/health are
configured identically and routers keep the exact same `/api/v1/...` paths they
had in the former monolith (Kong routes to a service by path prefix).
"""
import logging
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

logger = logging.getLogger("marketplace.observability")
_sentry_inited = False


def _init_sentry(service_name: str) -> None:
    """Initialise Sentry once per process (no-op without SENTRY_DSN)."""
    global _sentry_inited
    if _sentry_inited or not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk  # type: ignore
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            environment=settings.APP_ENV,
            release=settings.APP_VERSION,
        )
        sentry_sdk.set_tag("service", service_name)
        _sentry_inited = True
    except Exception as exc:  # noqa: BLE001 — observability must never break boot
        logger.warning("Sentry init failed: %s", exc)


def _init_metrics(app: FastAPI, service_name: str) -> None:
    """Expose Prometheus metrics at /metrics (no-op if lib missing/disabled)."""
    if not settings.METRICS_ENABLED:
        return
    try:
        from prometheus_fastapi_instrumentator import Instrumentator  # type: ignore
        Instrumentator(
            should_group_status_codes=True,
            excluded_handlers=["/metrics", "/health"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Prometheus metrics not enabled: %s", exc)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Ensure upload directories exist (local storage fallback; prod uses S3).
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "products"), exist_ok=True)
    yield


def create_service_app(service_name: str, routers: list) -> FastAPI:
    """Build a configured FastAPI app that mounts `routers` under /api/v1."""
    _init_sentry(service_name)

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

    # Prometheus /metrics (after routes are mounted).
    _init_metrics(app, service_name)

    return app

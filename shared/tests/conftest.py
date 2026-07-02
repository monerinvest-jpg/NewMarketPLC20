"""
Shared fixtures for the smoke-flow tests.

The smoke tests spin up ONE in-process FastAPI app that mounts the routers of
several services (identity + catalog + orders slices) over an in-memory SQLite
database — no Postgres/Redis/Kong required, so they run anywhere (CI included).
External integrations stay in their graceful-fallback modes: e-mail is logged,
the payment gateway fails into a pending payment, the cache is disabled.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Force fallback modes BEFORE app.core.config is imported.
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("METRICS_ENABLED", "false")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:63790/0")  # nonexistent
os.environ.setdefault("SENTRY_DSN", "")
# Writable scratch dir (the tests dir may be mounted read-only in containers).
os.environ.setdefault("UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "smoke_uploads"))

import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool


# SQLite autoincrements only INTEGER PRIMARY KEY — render the models' BIGINT
# ids as INTEGER on the sqlite dialect so inserts get generated ids like on PG.
@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(type_, compiler, **kw):
    return "INTEGER"


@pytest.fixture(scope="session")
def event_loop():
    """One loop for the whole session so the session-scoped app/engine and the
    per-test clients all run on the same loop (pytest-asyncio 0.23 pattern)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def app_and_sessionmaker():
    from app.core.database import get_db
    from app.models.models import Base, Category
    from app.service_factory import create_service_app

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(engine, expire_on_commit=False)

    # Minimal seed: one category (products require category_id).
    async with TestSession() as db:
        db.add(Category(name="Тестовая категория", slug="test-category"))
        await db.commit()

    from app.api.v1.endpoints.auth import router as auth_router
    from app.api.v1.endpoints.products import router as products_router
    from app.api.v1.endpoints.shops import router as shops_router
    from app.api.v1.endpoints.cart import router as cart_router
    from app.api.v1.endpoints.orders import router as orders_router

    app = create_service_app(
        "smoke",
        [auth_router, products_router, shops_router, cart_router, orders_router],
    )

    async def _get_test_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    yield app, TestSession
    await engine.dispose()


@pytest_asyncio.fixture()
async def client(app_and_sessionmaker):
    import httpx

    app, _ = app_and_sessionmaker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke") as c:
        yield c


@pytest.fixture()
def db_session(app_and_sessionmaker):
    """Factory for direct DB access inside tests (e.g. to activate a product)."""
    _, TestSession = app_and_sessionmaker
    return TestSession

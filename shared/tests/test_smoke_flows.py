"""
End-to-end smoke flows over the in-process app (see conftest.py):
registration/login, shop + product creation, catalog visibility & suggest,
cart operations and checkout into a pending-payment order.

These guard the money paths against regressions — they intentionally assert
coarse outcomes (status codes, core fields), not exact payload shapes.
"""
import pytest
from sqlalchemy import select

pytestmark = pytest.mark.asyncio

# NB: pydantic's EmailStr rejects reserved TLDs (.test/.example) — use a
# plausible real-world domain (syntax check only, no DNS lookup).
BUYER = {"email": "buyer@smoke-marketplace.ru", "password": "smoke-pass-123", "full_name": "Смоук Покупатель"}
SELLER = {"email": "seller@smoke-marketplace.ru", "password": "smoke-pass-123", "full_name": "Смоук Продавец", "role": "seller"}


async def _register_and_login(client, creds) -> dict:
    r = await client.post("/api/v1/auth/register", json=creds)
    assert r.status_code in (201, 400), r.text  # 400 = already registered (re-run)
    r = await client.post("/api/v1/auth/login", json={"email": creds["email"], "password": creds["password"]})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_register_login_me(client):
    headers = await _register_and_login(client, BUYER)
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == BUYER["email"]
    assert body["role"] == "buyer"


async def test_seller_creates_shop_and_product(client, db_session):
    headers = await _register_and_login(client, SELLER)

    # Shop with mandatory requisites (self-employed: 12-digit INN).
    r = await client.post("/api/v1/shops", headers=headers, json={
        "name": "Смоук-мастерская",
        "description": "Тестовый магазин",
        "requisites": {
            "tax_regime": "self_employed",
            "legal_name": "Смоук Продавец",
            "inn": "123456789012",
        },
    })
    assert r.status_code in (201, 400), r.text  # 400 = shop exists on re-run

    r = await client.post("/api/v1/products", headers=headers, json={
        "category_id": 1,
        "title": "Смоук-табурет из дуба",
        "description": "Ручная работа, смоук-тест",
        "price": "1500.00",
        "quantity": 5,
        "weight_g": 2000,
    })
    assert r.status_code == 201, r.text
    product = r.json()
    assert product["title"] == "Смоук-табурет из дуба"

    # Activate regardless of the premoderation default (mirrors admin approval).
    from app.models.models import Product, ProductStatus
    async with db_session() as db:
        p = await db.get(Product, product["id"])
        p.status = ProductStatus.active
        await db.commit()

    # Publicly visible in the catalog…
    r = await client.get(f"/api/v1/products/{product['id']}")
    assert r.status_code == 200
    r = await client.get("/api/v1/products", params={"q": "табурет"})
    assert r.status_code == 200
    assert any(i["id"] == product["id"] for i in r.json()["items"])

    # …and in header suggest + full-text search (DB fallback engine).
    r = await client.get("/api/v1/products/suggest", params={"q": "табурет"})
    assert r.status_code == 200
    assert any(p["id"] == product["id"] for p in r.json()["products"])
    r = await client.get("/api/v1/products/search", params={"q": "табурет"})
    assert r.status_code == 200
    assert r.json()["engine"] == "db"
    assert r.json()["total"] >= 1


async def test_cart_flow(client):
    headers = await _register_and_login(client, BUYER)

    # The product created by the seller test (ordering ensured by file order).
    r = await client.get("/api/v1/products", params={"q": "табурет"})
    product_id = r.json()["items"][0]["id"]

    r = await client.post("/api/v1/cart", headers=headers, json={"product_id": product_id, "quantity": 2})
    assert r.status_code in (200, 201), r.text

    r = await client.get("/api/v1/cart", headers=headers)
    assert r.status_code == 200
    items = r.json()
    line = next(i for i in items if i["product_id"] == product_id)
    assert line["quantity"] == 2

    r = await client.patch(f"/api/v1/cart/{line['id']}", headers=headers, json={"quantity": 1})
    assert r.status_code == 200, r.text


async def test_checkout_creates_pending_order(client, db_session):
    headers = await _register_and_login(client, BUYER)

    r = await client.post("/api/v1/orders", headers=headers, json={
        "delivery_address": "г. Москва, ул. Смоук-Тестовая, д. 1",
        "city_to": "Москва",
    })
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["items"], "order must contain the cart line"

    # No payment gateway in tests → the order stays awaiting payment with a
    # pending Payment row (the graceful-fallback path).
    assert order["status"] in ("pending_payment", "paid")

    from app.models.models import Payment
    async with db_session() as db:
        payment = (await db.execute(
            select(Payment).where(Payment.order_id == order["id"])
        )).scalar_one_or_none()
    assert payment is not None

    # Cart is emptied by checkout.
    r = await client.get("/api/v1/cart", headers=headers)
    assert r.status_code == 200
    assert r.json() == []

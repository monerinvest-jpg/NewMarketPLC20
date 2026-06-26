"""
Unit tests for pure business logic that doesn't require a database.

Run with:  pytest backend/tests -v

These cover the highest-risk calculations: multi-shop commission/payout math,
flash-sale effective price, slug generation, RBAC resolution, and the
moderation auto-flag heuristics' priority scoring.
"""
import os
import sys
from decimal import Decimal

# Make the app importable when running pytest from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ─── Commission / payout math ───────────────────────────────────────────────────

def test_commission_basic():
    from app.services.commission_service import calculate_item_financials
    fin = calculate_item_financials(Decimal("1000.00"), Decimal("10.00"))
    assert fin["platform_fee"] == Decimal("100.00")
    assert fin["seller_net"] == Decimal("900.00")


def test_commission_rounding():
    from app.services.commission_service import calculate_item_financials
    fin = calculate_item_financials(Decimal("333.33"), Decimal("15.00"))
    # 333.33 * 0.15 = 49.9995 -> 50.00
    assert fin["platform_fee"] == Decimal("50.00")
    assert fin["seller_net"] == Decimal("283.33")


def test_commission_sum_preserves_total():
    from app.services.commission_service import calculate_item_financials
    subtotal = Decimal("777.77")
    fin = calculate_item_financials(subtotal, Decimal("12.50"))
    assert fin["platform_fee"] + fin["seller_net"] == subtotal


def test_commission_zero():
    from app.services.commission_service import calculate_item_financials
    fin = calculate_item_financials(Decimal("500.00"), Decimal("0.00"))
    assert fin["platform_fee"] == Decimal("0.00")
    assert fin["seller_net"] == Decimal("500.00")


# ─── Flash-sale effective price ─────────────────────────────────────────────────

def test_effective_price():
    from app.services.stock_service import effective_price
    assert effective_price(Decimal("1000.00"), Decimal("20")) == Decimal("800.00")
    assert effective_price(Decimal("999.99"), Decimal("10")) == Decimal("899.99")


def test_effective_price_full_discount():
    from app.services.stock_service import effective_price
    assert effective_price(Decimal("100.00"), Decimal("99")) == Decimal("1.00")


# ─── Slug generation ────────────────────────────────────────────────────────────

def test_slugify_cyrillic():
    from app.services.slug_service import slugify
    assert slugify("Красная футболка") == "krasnaya-futbolka"


def test_slugify_strips_symbols():
    from app.services.slug_service import slugify
    s = slugify("Товар!!! №1 (новый)")
    assert " " not in s
    assert "!" not in s


def test_product_slug_has_id():
    from app.services.slug_service import product_slug
    assert product_slug("Чайник", 42).endswith("-42")


# ─── RBAC ───────────────────────────────────────────────────────────────────────

class _FakeUser:
    def __init__(self, role=None, is_superuser=False, permissions=None):
        from app.models.models import UserRole
        self.role = role or UserRole.buyer
        self.is_superuser = is_superuser
        self.permissions = permissions


def test_rbac_superadmin_has_all():
    from app.services.rbac_service import has_permission, ALL_PERMISSIONS
    from app.models.models import UserRole
    u = _FakeUser(role=UserRole.superadmin)
    for key in ALL_PERMISSIONS:
        assert has_permission(u, key)


def test_rbac_explicit_permission():
    from app.services.rbac_service import has_permission
    import json
    u = _FakeUser(permissions=json.dumps(["payouts.process"]))
    assert has_permission(u, "payouts.process")
    assert not has_permission(u, "users.manage")


def test_rbac_empty_permissions():
    from app.services.rbac_service import get_permissions
    u = _FakeUser(permissions=None)
    assert get_permissions(u) == []


def test_rbac_serialize_filters_invalid():
    from app.services.rbac_service import serialize_permissions
    import json
    out = json.loads(serialize_permissions(["payouts.process", "not_a_real_perm"]))
    assert "payouts.process" in out
    assert "not_a_real_perm" not in out


# ─── Moderation auto-flag priority ──────────────────────────────────────────────

def test_priority_stopwords_dominate():
    from app.services.moderation_service import priority_from_flags
    high = priority_from_flags(["Стоп-слова: оружие"], None)
    low = priority_from_flags(["Очень короткое описание"], None)
    assert high > low


def test_priority_accumulates():
    from app.services.moderation_service import priority_from_flags
    one = priority_from_flags(["Дубликат названия (2)"], None)
    two = priority_from_flags(["Дубликат названия (2)", "Цена аномально высокая для категории"], None)
    assert two > one


# ─── Discount stacking cap (logic mirror) ───────────────────────────────────────

def test_discount_cap_logic():
    """Mirror of the checkout cap: bonus+coupon must not exceed subtotal."""
    subtotal = Decimal("100.00")
    bonus = Decimal("80.00")
    coupon = Decimal("50.00")
    discount = bonus + coupon
    if discount > subtotal:
        overflow = discount - subtotal
        bonus = max(Decimal("0.00"), bonus - overflow)
        discount = bonus + coupon
        if discount > subtotal:
            discount = subtotal
    assert discount <= subtotal
    # overflow = 130-100 = 30; bonus trimmed 80-30 = 50; discount = 50+50 = 100
    assert discount == Decimal("100.00")
    assert bonus == Decimal("50.00")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))


# ─── Fiscalization (54-ФЗ) receipt builder ──────────────────────────────────────

def test_fiscal_customer_block_email_vs_phone():
    from app.services.fiscal_service import _customer_block
    assert _customer_block("buyer@example.com") == {"email": "buyer@example.com"}
    assert _customer_block("+79991234567") == {"phone": "+79991234567"}


def test_fiscal_money_two_decimals():
    from app.services.fiscal_service import _money
    assert _money(Decimal("1000")) == "1000.00"
    assert _money(Decimal("19.9")) == "19.90"


def test_fiscal_build_receipt_items_and_delivery():
    from app.services.fiscal_service import build_receipt
    line_items = [
        {"description": "Товар А", "quantity": 2, "unit_price": Decimal("500.00"), "vat_code": 1},
        {"description": "Товар Б", "quantity": 1, "unit_price": Decimal("300.00"), "vat_code": 4},
    ]
    receipt = build_receipt(
        "buyer@example.com", line_items,
        delivery_cost=Decimal("250.00"), tax_system_code=2,
    )
    # customer + tax system
    assert receipt["customer"] == {"email": "buyer@example.com"}
    assert receipt["tax_system_code"] == 2
    # 2 goods + 1 delivery line
    assert len(receipt["items"]) == 3
    first = receipt["items"][0]
    assert first["description"] == "Товар А"
    assert first["quantity"] == "2"
    assert first["amount"] == {"value": "500.00", "currency": "RUB"}
    assert first["vat_code"] == 1
    # delivery line is a service
    delivery = receipt["items"][-1]
    assert delivery["description"] == "Доставка"
    assert delivery["payment_subject"] == "service"
    assert delivery["amount"]["value"] == "250.00"


def test_fiscal_build_receipt_omits_tax_system_when_absent():
    from app.services.fiscal_service import build_receipt
    receipt = build_receipt(
        "buyer@example.com",
        [{"description": "X", "quantity": 1, "unit_price": Decimal("10.00"), "vat_code": 1}],
    )
    assert "tax_system_code" not in receipt
    assert len(receipt["items"]) == 1


# ─── Recommendations: purchased-status gating ───────────────────────────────────

def test_recommendation_purchased_statuses():
    from app.models.models import OrderStatus
    from app.services.recommendation_service import PURCHASED_STATUSES
    # Real purchases count toward co-purchase
    assert OrderStatus.paid in PURCHASED_STATUSES
    assert OrderStatus.completed in PURCHASED_STATUSES
    # Non-purchases must never inflate recommendations
    assert OrderStatus.pending_payment not in PURCHASED_STATUSES
    assert OrderStatus.cancelled not in PURCHASED_STATUSES
    assert OrderStatus.refunded not in PURCHASED_STATUSES

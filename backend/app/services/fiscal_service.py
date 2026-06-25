"""
Fiscalization service (54-ФЗ) using YooKassa's built-in fiscalization.

YooKassa registers the fiscal receipt in the ОФД on our behalf: we embed a
`receipt` object in the payment (income) or refund (income_refund) request, and
YooKassa reports the registration outcome back via webhook in the
`receipt_registration` field. This module builds those receipt objects from an
order and tracks the registration lifecycle in the FiscalReceipt table.

VAT codes (ЮKassa): 1=без НДС, 2=0%, 3=10%, 4=20%, 5=10/110, 6=20/120.
Tax system codes: 1=ОСН, 2=УСН доход, 3=УСН доход-расход, 4=ЕНВД, 5=ЕСХН, 6=Патент.
"""
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    FiscalReceipt, FiscalReceiptStatus, FiscalReceiptType, Order, SellerRequisites, User,
)

# Maps YooKassa's receipt_registration value (from the webhook) onto our status.
_REGISTRATION_STATUS = {
    "succeeded": FiscalReceiptStatus.succeeded,
    "pending": FiscalReceiptStatus.pending,
    "canceled": FiscalReceiptStatus.canceled,
    "cancelled": FiscalReceiptStatus.canceled,
}


def _money(value: Decimal) -> str:
    """YooKassa expects amounts as strings with exactly two decimals."""
    return f"{Decimal(value).quantize(Decimal('0.01'))}"


def customer_contact(buyer: User) -> str:
    """
    54-ФЗ requires a customer contact on the receipt. Prefer email; fall back to
    phone. Returns the raw contact string (the receipt dict wraps it correctly).
    """
    if buyer.email:
        return buyer.email
    if buyer.phone:
        return buyer.phone
    return ""


def _customer_block(contact: str) -> dict:
    """Wrap the contact into the receipt's `customer` object. A phone is sent in
    E.164-ish form; everything with an @ is treated as email."""
    if "@" in contact:
        return {"email": contact}
    return {"phone": contact}


def _vat_code_for(requisites: Optional[SellerRequisites]) -> int:
    if requisites is not None and requisites.vat_code:
        return requisites.vat_code
    return settings.FISCAL_VAT_CODE


def _tax_system_for(requisites: Optional[SellerRequisites]) -> Optional[int]:
    """Per-seller СНО if set, else platform default. 0 means 'do not send'."""
    if requisites is not None and requisites.tax_system_code:
        return requisites.tax_system_code
    code = settings.FISCAL_TAX_SYSTEM_CODE
    return code if code else None


def _item(
    description: str,
    quantity: int,
    unit_price: Decimal,
    vat_code: int,
    payment_subject: str,
    requisites: Optional[SellerRequisites] = None,
) -> dict:
    item: dict[str, Any] = {
        # ОФД limits the description to 128 chars.
        "description": (description or "Товар")[:128],
        "quantity": str(quantity),
        "amount": {"value": _money(unit_price), "currency": "RUB"},
        "vat_code": vat_code,
        "payment_subject": payment_subject,
        "payment_mode": settings.FISCAL_PAYMENT_MODE,
    }
    # Agent (marketplace) scheme: identify the actual supplier per item so the
    # receipt attributes the sale to the seller rather than the platform.
    if settings.FISCAL_AGENT_SCHEME and requisites is not None:
        item["agent_type"] = "agent"
        item["supplier"] = {"name": requisites.legal_name, "inn": requisites.inn}
    return item


def build_receipt(
    contact: str,
    line_items: list[dict],
    delivery_cost: Decimal = Decimal("0.00"),
    tax_system_code: Optional[int] = None,
) -> dict:
    """
    Build a YooKassa receipt object.

    `line_items` is a list of {"description", "quantity", "unit_price",
    "vat_code", "requisites"(optional)} dicts. A delivery line (payment_subject
    "service") is appended when delivery_cost > 0.
    """
    items: list[dict] = [
        _item(
            li["description"], li["quantity"], li["unit_price"], li["vat_code"],
            settings.FISCAL_PAYMENT_SUBJECT, li.get("requisites"),
        )
        for li in line_items
    ]
    if delivery_cost and delivery_cost > 0:
        items.append(_item(
            "Доставка", 1, delivery_cost, settings.FISCAL_VAT_CODE, "service",
        ))
    receipt: dict[str, Any] = {"customer": _customer_block(contact), "items": items}
    if tax_system_code:
        receipt["tax_system_code"] = tax_system_code
    return receipt


async def _requisites_by_shop(db: AsyncSession, shop_ids: set[int]) -> dict[int, SellerRequisites]:
    if not shop_ids:
        return {}
    rows = (await db.execute(
        select(SellerRequisites).where(SellerRequisites.shop_id.in_(shop_ids))
    )).scalars().all()
    return {r.shop_id: r for r in rows}


async def build_income_line_items(db: AsyncSession, item_ctx: list[dict]) -> tuple[list[dict], Optional[int]]:
    """
    From order item context (each: {title, quantity, unit_price, shop_id}) build
    the receipt line items with per-seller VAT, and resolve a single
    tax_system_code for the receipt (sellers on a marketplace receipt normally
    share one СНО; we take the first seller's, falling back to the platform).
    """
    shop_ids = {c["shop_id"] for c in item_ctx}
    req_map = await _requisites_by_shop(db, shop_ids)
    line_items: list[dict] = []
    for c in item_ctx:
        req = req_map.get(c["shop_id"])
        line_items.append({
            "description": c["title"],
            "quantity": c["quantity"],
            "unit_price": c["unit_price"],
            "vat_code": _vat_code_for(req),
            "requisites": req,
        })
    first_req = req_map.get(item_ctx[0]["shop_id"]) if item_ctx else None
    return line_items, _tax_system_for(first_req)


async def create_pending_receipt(
    db: AsyncSession,
    order: Order,
    receipt_type: FiscalReceiptType,
    contact: str,
    total: Decimal,
    receipt: dict,
    tax_system_code: Optional[int],
    payment_id: Optional[int] = None,
) -> FiscalReceipt:
    """Persist a FiscalReceipt snapshot in `pending` state."""
    fr = FiscalReceipt(
        order_id=order.id,
        payment_id=payment_id,
        type=receipt_type,
        status=FiscalReceiptStatus.pending,
        customer_contact=contact or "—",
        total=total,
        tax_system_code=tax_system_code,
        items_json=json.dumps(receipt.get("items", []), ensure_ascii=False),
    )
    db.add(fr)
    await db.flush()
    return fr


def apply_registration(fr: FiscalReceipt, registration: Optional[str], raw: Optional[dict] = None) -> None:
    """
    Update a receipt from a YooKassa `receipt_registration` value carried by the
    payment/refund webhook. Unknown/missing values leave the receipt pending.
    """
    if raw is not None:
        try:
            fr.raw_response = json.dumps(raw, ensure_ascii=False)[:60000]
        except Exception:
            pass
    new_status = _REGISTRATION_STATUS.get((registration or "").lower())
    if new_status is None:
        return
    fr.status = new_status
    if new_status == FiscalReceiptStatus.succeeded and fr.registered_at is None:
        fr.registered_at = datetime.now(timezone.utc)


def mark_failed(fr: FiscalReceipt, error: str) -> None:
    fr.status = FiscalReceiptStatus.failed
    fr.error = (error or "")[:500]


async def get_order_receipts(db: AsyncSession, order_id: int) -> list[FiscalReceipt]:
    rows = (await db.execute(
        select(FiscalReceipt).where(FiscalReceipt.order_id == order_id)
        .order_by(FiscalReceipt.created_at)
    )).scalars().all()
    return list(rows)

"""
Payment gateway abstraction.
Concrete implementations: YooKassa, CloudPayments (stub).
"""
import ipaddress
import json
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

import httpx

from app.core.config import settings

# YooKassa publishes the fixed set of IP ranges its webhook notifications
# originate from (see https://yookassa.ru/developers/using-api/webhooks#ip).
# A request claiming to be a YooKassa notification must originate from one
# of these ranges — this is how YooKassa expects webhooks to be verified,
# since it does not sign payloads with HMAC the way some other gateways do.
YOOKASSA_NOTIFICATION_IP_RANGES = [
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.156.11/32",
    "77.75.156.35/32",
    "77.75.154.128/25",
    "2a02:5180::/32",
]


def _ip_in_yookassa_range(ip_address: Optional[str]) -> bool:
    if not ip_address:
        return False
    try:
        addr = ipaddress.ip_address(ip_address)
    except ValueError:
        return False
    return any(addr in ipaddress.ip_network(net) for net in YOOKASSA_NOTIFICATION_IP_RANGES)


class PaymentResult:
    def __init__(self, gateway_payment_id: str, confirmation_url: str, status: str):
        self.gateway_payment_id = gateway_payment_id
        self.confirmation_url = confirmation_url
        self.status = status


class BasePaymentGateway(ABC):
    @abstractmethod
    async def create_payment(
        self,
        order_id: int,
        amount: Decimal,
        description: str,
        return_url: str,
        receipt: Optional[dict] = None,
    ) -> PaymentResult:
        ...

    @abstractmethod
    async def refund_payment(
        self,
        gateway_payment_id: str,
        amount: Decimal,
        receipt: Optional[dict] = None,
    ) -> bool:
        ...

    @abstractmethod
    def verify_webhook(self, body: bytes, headers: dict, source_ip: Optional[str] = None) -> bool:
        ...

    async def create_standalone_receipt(
        self,
        receipt_type: str,
        payment_or_refund_id: str,
        receipt: dict,
    ) -> dict:
        """
        Register a fiscal receipt independently of payment creation (used to
        retry a failed/pending receipt). Not all gateways support this.
        """
        raise NotImplementedError("Standalone receipts are not supported by this gateway")


class YooKassaGateway(BasePaymentGateway):
    BASE_URL = "https://api.yookassa.ru/v3"

    def __init__(self, shop_id: str, secret_key: str, return_url: str):
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.return_url = return_url

    def _auth(self):
        import base64
        cred = f"{self.shop_id}:{self.secret_key}"
        return base64.b64encode(cred.encode()).decode()

    async def create_payment(
        self,
        order_id: int,
        amount: Decimal,
        description: str,
        return_url: str,
        receipt: Optional[dict] = None,
    ) -> PaymentResult:
        idempotency_key = str(uuid.uuid4())
        payload = {
            "amount": {"value": str(amount), "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": return_url or self.return_url},
            "description": description,
            "metadata": {"order_id": str(order_id)},
            "capture": True,
        }
        # 54-ФЗ: embedding the receipt makes YooKassa register the fiscal
        # document in the ОФД automatically once the payment succeeds.
        if receipt:
            payload["receipt"] = receipt
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/payments",
                json=payload,
                headers={
                    "Authorization": f"Basic {self._auth()}",
                    "Idempotence-Key": idempotency_key,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        return PaymentResult(
            gateway_payment_id=data["id"],
            confirmation_url=data["confirmation"]["confirmation_url"],
            status=data["status"],
        )

    async def refund_payment(
        self, gateway_payment_id: str, amount: Decimal, receipt: Optional[dict] = None
    ) -> bool:
        idempotency_key = str(uuid.uuid4())
        payload = {
            "amount": {"value": str(amount), "currency": "RUB"},
            "payment_id": gateway_payment_id,
        }
        # 54-ФЗ: a refund receipt (возврат прихода) is registered alongside the
        # refund when the receipt object is supplied.
        if receipt:
            payload["receipt"] = receipt
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/refunds",
                json=payload,
                headers={
                    "Authorization": f"Basic {self._auth()}",
                    "Idempotence-Key": idempotency_key,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            return resp.status_code in (200, 201)

    async def create_standalone_receipt(
        self, receipt_type: str, payment_or_refund_id: str, receipt: dict
    ) -> dict:
        """
        Register a receipt via POST /receipts, referencing an existing payment
        (receipt_type="payment") or refund (receipt_type="refund"). Used to
        retry a receipt that failed to register with the original request.
        """
        idempotency_key = str(uuid.uuid4())
        payload = {
            "type": receipt_type,
            "send": True,
            "customer": receipt.get("customer", {}),
            "items": receipt.get("items", []),
        }
        if receipt_type == "payment":
            payload["payment_id"] = payment_or_refund_id
        else:
            payload["refund_id"] = payment_or_refund_id
        if "tax_system_code" in receipt:
            payload["tax_system_code"] = receipt["tax_system_code"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/receipts",
                json=payload,
                headers={
                    "Authorization": f"Basic {self._auth()}",
                    "Idempotence-Key": idempotency_key,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

    def verify_webhook(self, body: bytes, headers: dict, source_ip: Optional[str] = None) -> bool:
        """
        Verifies a YooKassa webhook notification two ways:
        1. The request must originate from one of YooKassa's published
           notification IP ranges (this is YooKassa's actual verification
           mechanism — it does not sign payloads with HMAC).
        2. The body must be valid, well-formed JSON with the expected shape.

        IP verification is skipped when no real shop credentials are
        configured (dev/mock mode), so the webhook flow stays testable
        locally without a real YooKassa account or public IP.
        """
        try:
            data = json.loads(body)
        except Exception:
            return False
        if "object" not in data or "type" not in data:
            return False

        if not self.shop_id or not self.secret_key:
            # No real credentials configured — running in mock mode, IP
            # verification would only ever reject legitimate local testing.
            return True

        return _ip_in_yookassa_range(source_ip)


class CloudPaymentsGateway(BasePaymentGateway):
    """Stub implementation of CloudPayments gateway."""

    def __init__(self, public_id: str, api_secret: str):
        self.public_id = public_id
        self.api_secret = api_secret

    async def create_payment(self, order_id, amount, description, return_url, receipt=None) -> PaymentResult:
        raise NotImplementedError("CloudPayments gateway is not yet configured")

    async def refund_payment(self, gateway_payment_id, amount, receipt=None) -> bool:
        raise NotImplementedError("CloudPayments gateway is not yet configured")

    def verify_webhook(self, body, headers, source_ip: Optional[str] = None) -> bool:
        raise NotImplementedError("CloudPayments gateway is not yet configured")


def get_payment_gateway() -> BasePaymentGateway:
    """Factory: returns configured payment gateway from settings."""
    return YooKassaGateway(
        shop_id=settings.YOOKASSA_SHOP_ID,
        secret_key=settings.YOOKASSA_SECRET_KEY,
        return_url=settings.YOOKASSA_RETURN_URL,
    )

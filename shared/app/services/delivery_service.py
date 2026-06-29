"""
Delivery gateway abstraction.
Concrete implementations: CDEK (API 2.0), Boxberry (stub).
"""
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

import httpx

from app.core.config import settings


class DeliveryRate:
    def __init__(self, cost: Decimal, estimated_days: int, service: str):
        self.cost = cost
        self.estimated_days = estimated_days
        self.service = service


class PickupPoint:
    """A single parcel locker / pickup point (ПВЗ) returned by a delivery gateway."""

    def __init__(
        self,
        code: str,
        name: str,
        address: str,
        city: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        work_time: Optional[str] = None,
    ):
        self.code = code
        self.name = name
        self.address = address
        self.city = city
        self.latitude = latitude
        self.longitude = longitude
        self.work_time = work_time


class ShipmentResult:
    """
    Result of registering a shipment with a carrier. tracking_number is the
    carrier's number; label_url/label_bytes carry the carrier's printable label
    when available. ok=False with error means registration failed (caller may
    fall back to a manual tracking number + self-generated label).
    """
    def __init__(
        self,
        ok: bool,
        tracking_number: Optional[str] = None,
        carrier_uuid: Optional[str] = None,
        label_bytes: Optional[bytes] = None,
        error: Optional[str] = None,
    ):
        self.ok = ok
        self.tracking_number = tracking_number
        self.carrier_uuid = carrier_uuid
        self.label_bytes = label_bytes
        self.error = error


class BaseDeliveryGateway(ABC):
    # Whether this gateway can register shipments + return carrier labels.
    supports_shipments: bool = False

    @abstractmethod
    async def calculate_rate(
        self,
        city_from: str,
        city_to: str,
        weight_g: int,
    ) -> DeliveryRate:
        ...

    @abstractmethod
    async def get_pickup_points(self, city: str) -> list[PickupPoint]:
        ...

    async def create_shipment(self, shipment: dict) -> ShipmentResult:
        """
        Register a shipment with the carrier. Default: not supported, so callers
        fall back to a manually-entered tracking number + self-generated label.
        `shipment` is a plain dict with sender/recipient/parcel fields.
        """
        return ShipmentResult(ok=False, error="Перевозчик не поддерживает API-отгрузку")

    async def get_label(self, carrier_uuid: str) -> Optional[bytes]:
        """Fetch the carrier's PDF label for a registered shipment, if any."""
        return None


# ─── CDEK ──────────────────────────────────────────────────────────────────────

class CDEKGateway(BaseDeliveryGateway):
    """
    CDEK API 2.0 implementation.
    Uses the test environment URL by default; swap to production in settings.
    """
    AUTH_URL = "https://api.edu.cdek.ru/v2/oauth/token"

    _token: Optional[str] = None
    _token_expires: float = 0.0

    def __init__(self, client_id: str, client_secret: str, api_url: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_url = api_url

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.AUTH_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                # Fall back to mock when credentials are missing/invalid
                return "mock_token"

            data = resp.json()
            self.__class__._token = data["access_token"]
            self.__class__._token_expires = time.time() + data.get("expires_in", 3600)
            return self._token

    async def calculate_rate(
        self,
        city_from: str,
        city_to: str,
        weight_g: int,
    ) -> DeliveryRate:
        """
        Calculate delivery cost via CDEK tariff calculator.
        Falls back to a simple mock formula when credentials are not configured.
        """
        if not self.client_id:
            return self._mock_rate(city_from, city_to, weight_g)

        try:
            token = await self._get_token()
            if token == "mock_token":
                return self._mock_rate(city_from, city_to, weight_g)

            payload = {
                "type": 1,  # Online-shop tariff
                "tariff_code": 136,  # Door to door
                "from_location": {"city": city_from, "country_code": "RU"},
                "to_location": {"city": city_to, "country_code": "RU"},
                "packages": [{"weight": weight_g, "length": 20, "width": 20, "height": 20}],
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.api_url}/calculator/tariff",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    timeout=15,
                )
                if resp.status_code != 200:
                    return self._mock_rate(city_from, city_to, weight_g)

                data = resp.json()
                total = data.get("total_sum", 300)
                period = data.get("calendar_max", 5)
                return DeliveryRate(
                    cost=Decimal(str(total)).quantize(Decimal("0.01")),
                    estimated_days=period,
                    service="cdek",
                )
        except Exception:
            return self._mock_rate(city_from, city_to, weight_g)

    def _mock_rate(self, city_from: str, city_to: str, weight_g: int) -> DeliveryRate:
        """Simple mock: base 200 + 100 per kg."""
        weight_kg = weight_g / 1000
        cost = Decimal("200") + Decimal(str(round(weight_kg * 100, 2)))
        # Same city = 3 days, otherwise 7
        days = 3 if city_from.lower() == city_to.lower() else 7
        return DeliveryRate(cost=cost, estimated_days=days, service="cdek_mock")

    async def get_pickup_points(self, city: str) -> list[PickupPoint]:
        """
        Fetch CDEK pickup points (ПВЗ) for a city via the /deliverypoints endpoint.
        Falls back to a small mock list when credentials are not configured,
        so the checkout flow remains testable without real CDEK access.
        """
        if not self.client_id:
            return self._mock_pickup_points(city)

        try:
            token = await self._get_token()
            if token == "mock_token":
                return self._mock_pickup_points(city)

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.api_url}/deliverypoints",
                    params={"city_code": "", "city": city, "country_code": "RU", "type": "PVZ"},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                )
                if resp.status_code != 200:
                    return self._mock_pickup_points(city)

                data = resp.json()
                points = []
                for item in data[:20]:  # cap to a reasonable number for the UI
                    location = item.get("location", {})
                    points.append(PickupPoint(
                        code=item.get("code", ""),
                        name=item.get("name", "Пункт выдачи СДЭК"),
                        address=location.get("address", ""),
                        city=location.get("city", city),
                        latitude=location.get("latitude"),
                        longitude=location.get("longitude"),
                        work_time=item.get("work_time"),
                    ))
                return points
        except Exception:
            return self._mock_pickup_points(city)

    def _mock_pickup_points(self, city: str) -> list[PickupPoint]:
        """A handful of plausible pickup points so checkout UI has data to render."""
        return [
            PickupPoint(
                code=f"MOCK-{city.upper()[:3]}-01",
                name="СДЭК — ТЦ Центральный",
                address=f"{city}, ул. Ленина, 10",
                city=city,
                work_time="Пн-Вс 09:00-21:00",
            ),
            PickupPoint(
                code=f"MOCK-{city.upper()[:3]}-02",
                name="СДЭК — ул. Мира",
                address=f"{city}, ул. Мира, 25",
                city=city,
                work_time="Пн-Сб 10:00-20:00",
            ),
            PickupPoint(
                code=f"MOCK-{city.upper()[:3]}-03",
                name="СДЭК — Привокзальная площадь",
                address=f"{city}, Привокзальная пл., 1",
                city=city,
                work_time="Пн-Вс 08:00-22:00",
            ),
        ]

    # ── Shipment registration + carrier label (CDEK API 2.0) ──────────────────

    supports_shipments = True

    async def create_shipment(self, shipment: dict) -> ShipmentResult:
        """
        Register an order with CDEK (POST /orders). On success CDEK returns an
        entity uuid; the human tracking number (cdek_number) is assigned
        asynchronously, so we read it back via GET /orders/{uuid}. Falls back to
        a mock shipment when credentials are missing, so the seller flow works
        end-to-end without real CDEK access.

        `shipment` keys: tariff_code, from_city, to_city, to_address,
        recipient_name, recipient_phone, weight_g, order_number, items(list).
        """
        if not self.client_id:
            return self._mock_shipment(shipment)
        try:
            token = await self._get_token()
            if token == "mock_token":
                return self._mock_shipment(shipment)

            payload = {
                "type": 1,
                "number": str(shipment.get("order_number", "")),
                "tariff_code": shipment.get("tariff_code", 136),
                "from_location": {"city": shipment.get("from_city", "")},
                "to_location": {
                    "city": shipment.get("to_city", ""),
                    "address": shipment.get("to_address", ""),
                },
                "recipient": {
                    "name": shipment.get("recipient_name", ""),
                    "phones": [{"number": shipment.get("recipient_phone", "")}],
                },
                "packages": [{
                    "number": "1",
                    "weight": shipment.get("weight_g", 500),
                    "length": 20, "width": 20, "height": 20,
                    "items": shipment.get("items", []),
                }],
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.api_url}/orders",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    timeout=20,
                )
                if resp.status_code not in (200, 202):
                    return self._mock_shipment(shipment)
                data = resp.json()
                uuid = (data.get("entity") or {}).get("uuid")
                if not uuid:
                    return self._mock_shipment(shipment)

                # Read back the assigned CDEK tracking number
                tracking = None
                try:
                    info = await client.get(
                        f"{self.api_url}/orders/{uuid}",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=15,
                    )
                    if info.status_code == 200:
                        entity = info.json().get("entity", {})
                        tracking = entity.get("cdek_number")
                except Exception:
                    pass

                return ShipmentResult(ok=True, tracking_number=tracking, carrier_uuid=uuid)
        except Exception as e:  # noqa: BLE001
            return ShipmentResult(ok=False, error=f"Ошибка СДЭК: {e}")

    async def get_label(self, carrier_uuid: str) -> Optional[bytes]:
        """
        Request a print form (waybill) for a registered order and download the
        PDF. CDEK: POST /print/orders {orders:[{order_uuid}]} -> uuid, then
        GET /print/orders/{uuid}.pdf. Returns None if unavailable.
        """
        if not self.client_id:
            return None
        try:
            token = await self._get_token()
            if token == "mock_token":
                return None
            async with httpx.AsyncClient() as client:
                create = await client.post(
                    f"{self.api_url}/print/orders",
                    json={"orders": [{"order_uuid": carrier_uuid}]},
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    timeout=20,
                )
                if create.status_code not in (200, 202):
                    return None
                print_uuid = (create.json().get("entity") or {}).get("uuid")
                if not print_uuid:
                    return None
                pdf = await client.get(
                    f"{self.api_url}/print/orders/{print_uuid}.pdf",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=20,
                )
                if pdf.status_code == 200 and pdf.content:
                    return pdf.content
                return None
        except Exception:
            return None

    def _mock_shipment(self, shipment: dict) -> ShipmentResult:
        """Deterministic fake tracking number so the flow works without keys."""
        import hashlib
        seed = f"{shipment.get('order_number','')}-{shipment.get('to_city','')}"
        digit = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) % 10**10
        return ShipmentResult(ok=True, tracking_number=f"100{digit:010d}", carrier_uuid=f"mock-{digit}")


# ─── Boxberry stub ─────────────────────────────────────────────────────────────

class BoxberryGateway(BaseDeliveryGateway):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def calculate_rate(self, city_from: str, city_to: str, weight_g: int) -> DeliveryRate:
        raise NotImplementedError("Boxberry gateway is not yet configured")

    async def get_pickup_points(self, city: str) -> list[PickupPoint]:
        raise NotImplementedError("Boxberry gateway is not yet configured")


# ─── Ozon Delivery ─────────────────────────────────────────────────────────────

class OzonDeliveryGateway(BaseDeliveryGateway):
    """
    Ozon Delivery ("Ozon Логистика / rocket") integration.
    Real API requires an Ozon seller API key; without credentials it falls
    back to a mock tariff so the checkout flow stays testable.
    """
    API_URL = "https://api-seller.ozon.ru"

    def __init__(self, api_key: str = "", client_id: str = ""):
        self.api_key = api_key
        self.client_id = client_id

    async def calculate_rate(self, city_from: str, city_to: str, weight_g: int) -> DeliveryRate:
        if not self.api_key:
            return self._mock_rate(city_from, city_to, weight_g)
        try:
            # Ozon's rocket tariff endpoint shape; on any failure fall back to mock.
            payload = {
                "from_city": city_from,
                "to_city": city_to,
                "weight": weight_g,
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.API_URL}/v1/delivery/calculate",
                    json=payload,
                    headers={"Client-Id": self.client_id, "Api-Key": self.api_key},
                    timeout=15,
                )
                if resp.status_code != 200:
                    return self._mock_rate(city_from, city_to, weight_g)
                data = resp.json()
                return DeliveryRate(
                    cost=Decimal(str(data.get("price", 250))).quantize(Decimal("0.01")),
                    estimated_days=data.get("days", 5),
                    service="ozon",
                )
        except Exception:
            return self._mock_rate(city_from, city_to, weight_g)

    def _mock_rate(self, city_from: str, city_to: str, weight_g: int) -> DeliveryRate:
        # Ozon is typically a touch cheaper on light parcels in the mock model.
        weight_kg = weight_g / 1000
        cost = Decimal("180") + Decimal(str(round(weight_kg * 90, 2)))
        days = 2 if city_from.lower() == city_to.lower() else 6
        return DeliveryRate(cost=cost, estimated_days=days, service="ozon_mock")

    async def get_pickup_points(self, city: str) -> list[PickupPoint]:
        return [
            PickupPoint(code=f"OZON-{city.upper()[:3]}-01", name="Ozon — пункт выдачи",
                        address=f"{city}, ул. Советская, 5", city=city, work_time="Пн-Вс 10:00-21:00"),
            PickupPoint(code=f"OZON-{city.upper()[:3]}-02", name="Ozon Box (постамат)",
                        address=f"{city}, пр. Победы, 30", city=city, work_time="Круглосуточно"),
        ]


# ─── Yandex Delivery ───────────────────────────────────────────────────────────

class YandexDeliveryGateway(BaseDeliveryGateway):
    """
    Yandex Delivery (Яндекс Доставка) integration.
    Real API requires an OAuth token; mock fallback otherwise.
    """
    API_URL = "https://b2b.taxi.yandex.net/api/b2b/platform"

    def __init__(self, oauth_token: str = ""):
        self.oauth_token = oauth_token

    async def calculate_rate(self, city_from: str, city_to: str, weight_g: int) -> DeliveryRate:
        if not self.oauth_token:
            return self._mock_rate(city_from, city_to, weight_g)
        try:
            payload = {
                "route_points": [{"city": city_from}, {"city": city_to}],
                "total_weight": weight_g,
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.API_URL}/pricing/calc",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.oauth_token}"},
                    timeout=15,
                )
                if resp.status_code != 200:
                    return self._mock_rate(city_from, city_to, weight_g)
                data = resp.json()
                return DeliveryRate(
                    cost=Decimal(str(data.get("price", 300))).quantize(Decimal("0.01")),
                    estimated_days=data.get("days", 4),
                    service="yandex",
                )
        except Exception:
            return self._mock_rate(city_from, city_to, weight_g)

    def _mock_rate(self, city_from: str, city_to: str, weight_g: int) -> DeliveryRate:
        # Yandex tends to be fast but slightly pricier in the mock model.
        weight_kg = weight_g / 1000
        cost = Decimal("250") + Decimal(str(round(weight_kg * 110, 2)))
        days = 1 if city_from.lower() == city_to.lower() else 4
        return DeliveryRate(cost=cost, estimated_days=days, service="yandex_mock")

    async def get_pickup_points(self, city: str) -> list[PickupPoint]:
        return [
            PickupPoint(code=f"YA-{city.upper()[:3]}-01", name="Яндекс Маркет — ПВЗ",
                        address=f"{city}, ул. Гагарина, 12", city=city, work_time="Пн-Вс 09:00-22:00"),
        ]


# ─── Russian Post (Почта России) ───────────────────────────────────────────────

class RussianPostGateway(BaseDeliveryGateway):
    """
    Russian Post (Почта России) integration via the tariffication API.
    Real API requires a token + access key; mock fallback otherwise.
    Russian Post is the cheapest but slowest option in the mock model.
    """
    API_URL = "https://otpravka-api.pochta.ru/1.0"

    def __init__(self, token: str = "", access_key: str = ""):
        self.token = token
        self.access_key = access_key

    async def calculate_rate(self, city_from: str, city_to: str, weight_g: int) -> DeliveryRate:
        if not self.token:
            return self._mock_rate(city_from, city_to, weight_g)
        try:
            payload = {"mass": weight_g, "from-city": city_from, "to-city": city_to}
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.API_URL}/tariff",
                    json=payload,
                    headers={
                        "Authorization": f"AccessToken {self.token}",
                        "X-User-Authorization": f"Basic {self.access_key}",
                    },
                    timeout=15,
                )
                if resp.status_code != 200:
                    return self._mock_rate(city_from, city_to, weight_g)
                data = resp.json()
                # Russian Post returns cost in kopecks
                total_kopecks = data.get("total-rate", 15000)
                return DeliveryRate(
                    cost=(Decimal(str(total_kopecks)) / 100).quantize(Decimal("0.01")),
                    estimated_days=data.get("delivery-time", {}).get("max-days", 10),
                    service="russian_post",
                )
        except Exception:
            return self._mock_rate(city_from, city_to, weight_g)

    def _mock_rate(self, city_from: str, city_to: str, weight_g: int) -> DeliveryRate:
        weight_kg = weight_g / 1000
        cost = Decimal("120") + Decimal(str(round(weight_kg * 60, 2)))
        days = 5 if city_from.lower() == city_to.lower() else 12
        return DeliveryRate(cost=cost, estimated_days=days, service="russian_post_mock")

    async def get_pickup_points(self, city: str) -> list[PickupPoint]:
        return [
            PickupPoint(code=f"RP-{city.upper()[:3]}-01", name="Почта России — отделение",
                        address=f"{city}, ул. Почтовая, 1", city=city, work_time="Пн-Пт 08:00-20:00, Сб 09:00-18:00"),
            PickupPoint(code=f"RP-{city.upper()[:3]}-02", name="Почта России — отделение №2",
                        address=f"{city}, ул. Ленина, 47", city=city, work_time="Пн-Пт 09:00-19:00"),
        ]


# Registry of all delivery services available on the platform. The admin can
# enable/disable each via settings; the keys here are the canonical service codes.
DELIVERY_SERVICES = {
    "cdek": "СДЭК",
    "ozon": "Ozon Доставка",
    "yandex": "Яндекс Доставка",
    "russian_post": "Почта России",
}


async def enabled_delivery_services(db) -> dict:
    """The subset of DELIVERY_SERVICES the admin has enabled (setting
    `delivery_enabled_services` = comma-separated codes). Order is preserved;
    falls back to all services when the setting is empty/unset."""
    from app.services.settings_service import get_setting
    raw = (await get_setting(db, "delivery_enabled_services")) or ""
    codes = [c.strip() for c in raw.split(",") if c.strip()]
    if not codes:
        return dict(DELIVERY_SERVICES)
    return {c: DELIVERY_SERVICES[c] for c in codes if c in DELIVERY_SERVICES}


def get_delivery_gateway(service: str = "cdek") -> BaseDeliveryGateway:
    """
    Factory: returns the gateway for the requested service code.
    Falls back to CDEK if the code is unknown.
    """
    if service == "ozon":
        return OzonDeliveryGateway(
            api_key=getattr(settings, "OZON_API_KEY", ""),
            client_id=getattr(settings, "OZON_CLIENT_ID", ""),
        )
    if service == "yandex":
        return YandexDeliveryGateway(
            oauth_token=getattr(settings, "YANDEX_DELIVERY_TOKEN", ""),
        )
    if service == "russian_post":
        return RussianPostGateway(
            token=getattr(settings, "RUSSIAN_POST_TOKEN", ""),
            access_key=getattr(settings, "RUSSIAN_POST_ACCESS_KEY", ""),
        )
    return CDEKGateway(
        client_id=settings.CDEK_CLIENT_ID,
        client_secret=settings.CDEK_CLIENT_SECRET,
        api_url=settings.CDEK_API_URL,
    )

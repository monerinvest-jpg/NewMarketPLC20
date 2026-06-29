"""
Settings service: read/write all platform settings from the `settings` table.
Provides typed helpers for common settings like global commission, referral params.
"""
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.models import Setting

# Default values used when a setting is not yet in the DB
DEFAULTS: Dict[str, str] = {
    "global_commission_percent": "10.0",
    "enable_premoderation": "true",
    "enable_review_premoderation": "true",
    "enable_paid_placement": "false",
    "enable_loyalty_cashback": "true",
    "loyalty_cashback_percent": "5",
    "referral_buyer_bonus_percent": "5",
    "referral_buyer_min_order_amount": "1000",
    "referral_seller_bonus_percent": "10",
    "referral_bonus_max_discount_percent": "30",
    "site_name": "Marketplace",
    "site_description": "Лучший маркетплейс уникальных товаров",
    "support_email": "support@marketplace.com",
    "yookassa_shop_id": "",
    "yookassa_secret_key": "",
    "cdek_client_id": "",
    "cdek_client_secret": "",
    "order_auto_complete_days": "7",
    "order_auto_delivered_days": "14",
    # SMS via SMSC.ru — DISABLED by default. Toggle in admin → SMS section.
    "sms_enabled": "false",
    "smsc_login": "",
    "smsc_password": "",
    "smsc_sender": "",
    "smsc_use_apikey": "false",
    "sms_notify_order_status": "false",
    "sms_notify_phone_verification": "true",
    # Observability: a Grafana dashboard URL embedded in admin → Метрики (iframe).
    # Use a shared/anonymous or kiosk-mode URL; empty hides the embed.
    "grafana_dashboard_url": "",
    # Trust & KYC. VIP badge can be bought (vip_price for vip_duration_days) or
    # earned by reputation (rating ≥ min AND reviews ≥ min). KYC = document check.
    "trust_badges_enabled": "true",
    "vip_price": "990",
    "vip_duration_days": "30",
    "vip_auto_rating_min": "4.8",
    "vip_auto_reviews_min": "50",
    "kyc_required_for_payout": "false",
    # Multi-delivery: comma-separated service codes enabled at checkout
    # (cdek, ozon, yandex, russian_post). Empty = all enabled.
    "delivery_enabled_services": "cdek,ozon,yandex,russian_post",
}

DESCRIPTIONS: Dict[str, str] = {
    "global_commission_percent": "Глобальная комиссия платформы, % (применяется если у магазина нет индивидуальной)",
    "enable_premoderation": "Включить премодерацию товаров (true/false)",
    "enable_review_premoderation": "Включить премодерацию отзывов (true/false)",
    "enable_paid_placement": "Включить платное размещение продавцов / тарифные планы (true/false)",
    "enable_loyalty_cashback": "Включить начисление кэшбэка баллами за покупки (true/false)",
    "loyalty_cashback_percent": "Процент кэшбэка баллами от суммы завершённого заказа",
    "referral_buyer_bonus_percent": "Бонус за привлечённого покупателя, % от его первой покупки (начисляется баллами)",
    "referral_buyer_min_order_amount": "Минимальная сумма первой покупки для начисления реферального бонуса, ₽",
    "referral_seller_bonus_percent": "Вознаграждение за привлечённого продавца, % от его первой продажи",
    "referral_bonus_max_discount_percent": "Макс. % от суммы заказа, который можно покрыть бонусами",
    "site_name": "Название сайта",
    "site_description": "Описание сайта",
    "support_email": "Email службы поддержки",
    "yookassa_shop_id": "YooKassa Shop ID",
    "yookassa_secret_key": "YooKassa Secret Key",
    "cdek_client_id": "CDEK Client ID",
    "cdek_client_secret": "CDEK Client Secret",
    "order_auto_complete_days": "Дней до автозавершения заказа после доставки",
    "order_auto_delivered_days": "Дней до автометки 'доставлен' после отправки",
    "sms_enabled": "Включить SMS-функции через SMSC.ru (true/false). По умолчанию выключено.",
    "smsc_login": "Логин аккаунта SMSC.ru",
    "smsc_password": "Пароль SMSC.ru (или API-ключ, если включён режим apikey)",
    "smsc_sender": "Имя отправителя SMS (sender ID, зарегистрированный в SMSC.ru)",
    "smsc_use_apikey": "Использовать API-ключ вместо логина/пароля (true/false)",
    "sms_notify_order_status": "Отправлять SMS при смене статуса заказа (true/false)",
    "sms_notify_phone_verification": "Отправлять SMS-код для подтверждения телефона (true/false)",
}


async def get_all_settings(db: AsyncSession) -> Dict[str, Setting]:
    result = await db.execute(select(Setting))
    rows = result.scalars().all()
    stored = {row.key: row for row in rows}

    # Ensure all defaults exist in DB
    for key, default_value in DEFAULTS.items():
        if key not in stored:
            setting = Setting(
                key=key,
                value=default_value,
                description=DESCRIPTIONS.get(key),
            )
            db.add(setting)
            stored[key] = setting

    await db.flush()
    return stored


async def get_setting(db: AsyncSession, key: str) -> str:
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        return DEFAULTS.get(key, "")
    return setting.value


async def set_setting(db: AsyncSession, key: str, value: str) -> Setting:
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = Setting(
            key=key,
            value=value,
            description=DESCRIPTIONS.get(key),
        )
        db.add(setting)
    else:
        setting.value = value
    await db.flush()
    return setting


async def get_global_commission(db: AsyncSession) -> Decimal:
    val = await get_setting(db, "global_commission_percent")
    return Decimal(val)


async def is_premoderation_enabled(db: AsyncSession) -> bool:
    val = await get_setting(db, "enable_premoderation")
    return val.lower() == "true"


async def is_review_premoderation_enabled(db: AsyncSession) -> bool:
    val = await get_setting(db, "enable_review_premoderation")
    return val.lower() == "true"


async def get_referral_settings(db: AsyncSession) -> Dict[str, Decimal]:
    keys = [
        "referral_buyer_bonus_percent",
        "referral_buyer_min_order_amount",
        "referral_seller_bonus_percent",
        "referral_bonus_max_discount_percent",
    ]
    out = {}
    for key in keys:
        val = await get_setting(db, key)
        out[key] = Decimal(val)
    return out

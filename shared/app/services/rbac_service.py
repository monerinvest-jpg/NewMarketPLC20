"""
RBAC service. Granular permissions layered on top of the coarse role. The
permission list lives as JSON on User.permissions; superadmins implicitly have
everything. Used to gate specific admin actions beyond the role check.
"""
import json
from typing import Optional

from app.models.models import User, UserRole

# Catalog of grantable permissions (key -> human description).
ALL_PERMISSIONS = {
    "moderate.products": "Модерация товаров",
    "moderate.shops": "Модерация магазинов",
    "moderate.reviews": "Модерация отзывов и жалоб",
    "catalog.manage": "Управление каталогом (категории, очередь)",
    "orders.manage": "Управление заказами и чеками",
    "payouts.process": "Обработка выводов средств",
    "marketing.manage": "Маркетинг (купоны, баннеры, сертификаты, лояльность, рефералы)",
    "users.manage": "Управление пользователями (роли, права, баланс)",
    "users.view": "Просмотр данных пользователей и продавцов",
    "support.handle": "Работа с обращениями поддержки",
    "support.manage": "Руководство поддержкой (назначение, статистика)",
    "settings.edit": "Изменение настроек платформы",
    "analytics.view": "Просмотр аналитики",
    "feature_flags.manage": "Управление feature flags",
    "audit.view": "Просмотр журнала действий",
}

# How the admin sidebar maps onto permissions: each destination (path -> label)
# requires one permission. The user's effective permissions therefore decide
# exactly which menu items they see — so granting a permission "lights up" the
# corresponding section. Superadmins implicitly hold every permission.
MENU_ITEMS = [
    ("/admin", "Дашборд", "analytics.view"),
    ("/admin/platform-analytics", "Аналитика платформы", "analytics.view"),
    ("/admin/cohorts", "Когорты и LTV", "analytics.view"),
    ("/admin/reconciliation", "Реконсиляция", "analytics.view"),
    ("/admin/users", "Пользователи", "users.view"),
    ("/admin/shops", "Магазины", "users.view"),
    ("/admin/moderators", "Модераторы", "users.manage"),
    ("/admin/products", "Товары", "moderate.products"),
    ("/admin/moderation-queue", "Очередь модерации", "moderate.products"),
    ("/admin/categories", "Категории", "catalog.manage"),
    ("/admin/reviews", "Отзывы", "moderate.reviews"),
    ("/admin/orders", "Заказы", "orders.manage"),
    ("/admin/payouts", "Выводы средств", "payouts.process"),
    ("/admin/fiscal-receipts", "Фискальные чеки", "orders.manage"),
    ("/admin/coupons", "Купоны", "marketing.manage"),
    ("/admin/banners", "Баннеры", "marketing.manage"),
    ("/admin/gift-certificates", "Сертификаты", "marketing.manage"),
    ("/admin/loyalty-tiers", "Лояльность", "marketing.manage"),
    ("/admin/referrals", "Рефералы", "marketing.manage"),
    ("/admin/plans", "Тарифы", "settings.edit"),
    ("/admin/paid-features", "Платные возможности", "settings.edit"),
    ("/admin/currencies", "Валюты", "settings.edit"),
    ("/admin/reports", "Жалобы", "moderate.reviews"),
    ("/admin/feature-flags", "Feature flags", "feature_flags.manage"),
    ("/admin/sms", "SMS (SMSC.ru)", "settings.edit"),
    ("/admin/audit-log", "Журнал действий", "audit.view"),
    ("/admin/settings", "Настройки", "settings.edit"),
]

# Permission editor layout: grouped to mirror the sidebar sections.
PERMISSION_GROUPS = [
    {"group": "Обзор и аналитика", "keys": ["analytics.view", "audit.view"]},
    {"group": "Люди и магазины", "keys": ["users.view", "users.manage"]},
    {"group": "Каталог и модерация", "keys": ["moderate.products", "moderate.shops", "moderate.reviews", "catalog.manage"]},
    {"group": "Продажи и финансы", "keys": ["orders.manage", "payouts.process"]},
    {"group": "Маркетинг", "keys": ["marketing.manage"]},
    {"group": "Платформа и настройки", "keys": ["settings.edit", "feature_flags.manage"]},
    {"group": "Поддержка", "keys": ["support.handle", "support.manage"]},
]


def menu_for_permission(key: str) -> list[dict]:
    """The sidebar items a given permission unlocks (path + label)."""
    return [{"path": p, "label": lbl} for (p, lbl, perm) in MENU_ITEMS if perm == key]


def allowed_menu_paths(user: User) -> list[str]:
    """Admin sidebar paths the user may see, given their effective permissions."""
    perms = set(get_permissions(user))
    if user.role == UserRole.superadmin or user.is_superuser:
        return [p for (p, _lbl, _perm) in MENU_ITEMS]
    return [p for (p, _lbl, perm) in MENU_ITEMS if perm in perms]

# Permissions implicitly granted by role, on top of any explicit per-user grants.
# Support agents can handle tickets and view (read-only) user/seller data.
# Moderators additionally lead support and view data; superadmin gets everything.
ROLE_DEFAULT_PERMISSIONS = {
    UserRole.support: ["support.handle", "users.view"],
    UserRole.moderator: [
        "support.handle", "support.manage", "users.view",
        "moderate.products", "moderate.shops", "moderate.reviews",
    ],
}


def get_permissions(user: User) -> list[str]:
    """Resolve the effective permission keys for a user."""
    if user.role == UserRole.superadmin or user.is_superuser:
        return list(ALL_PERMISSIONS.keys())
    # Role-based defaults (e.g. support/moderator) merged with explicit grants.
    perms = set(ROLE_DEFAULT_PERMISSIONS.get(user.role, []))
    if user.permissions:
        try:
            perms.update(json.loads(user.permissions))
        except (json.JSONDecodeError, TypeError):
            pass
    return [k for k in perms if k in ALL_PERMISSIONS]


def has_permission(user: User, key: str) -> bool:
    """True if the user holds the given permission (superadmin always does)."""
    if user.role == UserRole.superadmin or user.is_superuser:
        return True
    return key in get_permissions(user)


def serialize_permissions(keys: list[str]) -> str:
    """Validate against the catalog and serialize for storage."""
    valid = [k for k in keys if k in ALL_PERMISSIONS]
    return json.dumps(valid)

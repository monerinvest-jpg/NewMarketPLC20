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
    "moderate.reviews": "Модерация отзывов",
    "payouts.process": "Обработка выводов средств",
    "users.manage": "Управление пользователями",
    "users.view": "Просмотр данных пользователей и продавцов",
    "support.handle": "Работа с обращениями поддержки",
    "support.manage": "Руководство поддержкой (назначение, статистика)",
    "settings.edit": "Изменение настроек платформы",
    "analytics.view": "Просмотр аналитики",
    "feature_flags.manage": "Управление feature flags",
    "audit.view": "Просмотр журнала действий",
}

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

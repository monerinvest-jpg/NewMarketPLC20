"""
Multi-user shop accounts. A shop owner (Shop.owner_id) implicitly has every
permission. Managers also get everything. Staff get only the permission keys
explicitly granted to them (stored as a JSON list on ShopMember.permissions).

Mirrors the admin RBAC idea: each granted permission lights up a section of the
seller cabinet, so the management UI can show what a grant unlocks.
"""
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Shop, ShopMember, ShopMemberRole, User, UserRole

# Granular shop-staff permissions (key -> human label).
SHOP_PERMISSIONS = {
    "products.manage": "Товары (создание/редактирование)",
    "orders.manage": "Заказы и отгрузка",
    "promo.manage": "Акции, промокоды и наборы",
    "chat.handle": "Чат с покупателями",
    "reviews.reply": "Ответы на отзывы",
    "analytics.view": "Аналитика продаж",
    "finance.manage": "Финансы, выводы и тариф",
    "shop.edit": "Настройки магазина и реквизиты",
}

# Which seller-cabinet routes each permission unlocks (path -> label, permission).
SHOP_MENU_ITEMS = [
    ("/seller", "Обзор", None),  # always visible to any member
    ("/seller/products", "Товары", "products.manage"),
    ("/seller/orders", "Заказы", "orders.manage"),
    ("/seller/inventory", "Склад", "products.manage"),
    ("/seller/import", "Импорт товаров", "products.manage"),
    ("/seller/flash-sales", "Акции и распродажи", "promo.manage"),
    ("/seller/promo-rules", "Акции и наборы", "promo.manage"),
    ("/seller/coupons", "Промокоды", "promo.manage"),
    ("/seller/promotion", "Продвижение", "promo.manage"),
    ("/seller/reviews", "Отзывы", "reviews.reply"),
    ("/seller/analytics", "Аналитика", "analytics.view"),
    ("/seller/payouts", "Вывод средств", "finance.manage"),
    ("/seller/plan", "Тариф и комиссия", "finance.manage"),
    ("/seller/requisites", "Реквизиты", "shop.edit"),
    ("/seller/shop", "Настройки магазина", "shop.edit"),
    ("/seller/chat-templates", "Чат: шаблоны", "chat.handle"),
    ("/seller/returns", "Возвраты", "orders.manage"),
    ("/seller/disputes", "Споры", "orders.manage"),
    ("/seller/staff", "Сотрудники", None),  # owner-only, gated in the endpoint
]

PERMISSION_GROUPS = [
    {"group": "Каталог", "keys": ["products.manage"]},
    {"group": "Продажи", "keys": ["orders.manage", "promo.manage"]},
    {"group": "Клиенты", "keys": ["chat.handle", "reviews.reply"]},
    {"group": "Финансы и управление", "keys": ["analytics.view", "finance.manage", "shop.edit"]},
]


def menu_for_permission(key: str) -> list[dict]:
    return [{"path": p, "label": lbl} for (p, lbl, perm) in SHOP_MENU_ITEMS if perm == key]


def _parse(perms: Optional[str]) -> set[str]:
    if not perms:
        return set()
    try:
        return {k for k in json.loads(perms) if k in SHOP_PERMISSIONS}
    except (json.JSONDecodeError, TypeError):
        return set()


def serialize_permissions(keys: list[str]) -> str:
    return json.dumps([k for k in keys if k in SHOP_PERMISSIONS])


async def owned_shop(db: AsyncSession, user: User) -> Optional[Shop]:
    return (await db.execute(select(Shop).where(Shop.owner_id == user.id))).scalar_one_or_none()


async def get_membership(db: AsyncSession, user_id: int, shop_id: int) -> Optional[ShopMember]:
    return (await db.execute(
        select(ShopMember).where(ShopMember.shop_id == shop_id, ShopMember.user_id == user_id)
    )).scalar_one_or_none()


async def resolve_shop_id(db: AsyncSession, user: User) -> Optional[int]:
    """The shop this user acts on: the one they own, else one they're a member of."""
    own = (await db.execute(select(Shop.id).where(Shop.owner_id == user.id))).scalar_one_or_none()
    if own:
        return own
    return (await db.execute(
        select(ShopMember.shop_id).where(ShopMember.user_id == user.id).limit(1)
    )).scalar_one_or_none()


async def is_owner(db: AsyncSession, user: User, shop_id: int) -> bool:
    owner_id = (await db.execute(select(Shop.owner_id).where(Shop.id == shop_id))).scalar_one_or_none()
    return owner_id == user.id or user.role == UserRole.superadmin


async def shop_permissions(db: AsyncSession, user: User, shop_id: int) -> set[str]:
    """Effective permissions of a user for a shop (owner/manager → all)."""
    if await is_owner(db, user, shop_id):
        return set(SHOP_PERMISSIONS.keys())
    member = await get_membership(db, user.id, shop_id)
    if not member:
        return set()
    if member.role in (ShopMemberRole.owner, ShopMemberRole.manager):
        return set(SHOP_PERMISSIONS.keys())
    return _parse(member.permissions)


async def has_shop_permission(db: AsyncSession, user: User, shop_id: int, key: str) -> bool:
    return key in await shop_permissions(db, user, shop_id)


async def allowed_seller_paths(db: AsyncSession, user: User, shop_id: int) -> list[str]:
    perms = await shop_permissions(db, user, shop_id)
    owner = await is_owner(db, user, shop_id)
    out = []
    for path, _lbl, perm in SHOP_MENU_ITEMS:
        if path == "/seller/staff" and not owner:
            continue
        if perm is None or perm in perms:
            out.append(path)
    return out


async def is_shop_member(db: AsyncSession, user: User) -> bool:
    """True if the user owns a shop OR is staff of one (used to grant cabinet access)."""
    if await owned_shop(db, user):
        return True
    return (await db.execute(
        select(ShopMember.id).where(ShopMember.user_id == user.id).limit(1)
    )).scalar_one_or_none() is not None

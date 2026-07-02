"""
Admin API — Catalog administration: categories CRUD (+slug/descendant helpers), recommendations rebuild.

Split out of the former monolithic admin.py; mounted via the admin hub
(app.api.v1.endpoints.admin), same /admin prefix and RBAC dependencies.
"""
"""
Admin API endpoints. All require moderator or superadmin role.
"""
from decimal import Decimal
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_moderator_or_admin, get_current_superadmin, get_current_seller
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.models import (
    BalanceTransaction, BalanceTransactionType, Coupon, FiscalReceipt, FiscalReceiptStatus,
    FiscalReceiptType, Order, OrderItem, OrderStatus,
    Payment, PaymentStatus, Product, ProductStatus, Referral, Report, ReportStatus,
    Review, ReviewStatus, Shop, Transaction, TransactionType, User, UserRole, Category, Setting,
)
from app.schemas.schemas import (
    BulkSettingsUpdate, CouponCreate, CouponOut, DashboardStats,
    FiscalReceiptOut,
    OrderOut, OrderStatusUpdate, ProductModerationUpdate, ProductOut,
    ReportOut, ReportUpdate, SettingOut, SettingUpdate,
    ShopAdminUpdate, ShopOut, UserAdminUpdate, UserOut, CategoryCreate, CategoryOut, CategoryUpdate,
    ReviewOut, ReviewModerationUpdate,
    FeatureFlagOut, FeatureFlagUpsert, UserPermissionsUpdate, AdminBalanceAdjust,
)
from app.services import fiscal_service
from app.services.settings_service import get_all_settings, set_setting

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/recommendations/rebuild")
async def rebuild_recommendations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """Recompute the materialized "bought together" co-purchase signal now.
    Normally this runs nightly; this endpoint forces an immediate refresh."""
    from app.services import recommendation_service
    pairs = await recommendation_service.rebuild_co_purchase(db)
    await db.commit()
    return {"status": "ok", "pairs": pairs}


# ─── Categories ───────────────────────────────────────────────────────────────

def _cat_out(c: Category) -> CategoryOut:
    """Build a CategoryOut without touching the lazy `children` relationship."""
    return CategoryOut(
        id=c.id, parent_id=c.parent_id, name=c.name, slug=c.slug,
        image=c.image, sort_order=c.sort_order, kind=c.kind, children=[],
    )


async def _unique_category_slug(db: AsyncSession, base: str, exclude_id: int | None = None) -> str:
    """Ensure the slug is unique across categories, suffixing -2, -3, ... if needed."""
    from app.services.slug_service import slugify
    base = slugify(base) or "category"
    candidate, n = base, 1
    while True:
        q = select(Category.id).where(Category.slug == candidate)
        if exclude_id is not None:
            q = q.where(Category.id != exclude_id)
        if (await db.execute(q)).scalar_one_or_none() is None:
            return candidate
        n += 1
        candidate = f"{base}-{n}"


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories_admin(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """Full category tree (any depth), built from a single flat load."""
    cats = (await db.execute(
        select(Category).order_by(Category.sort_order, Category.name)
    )).scalars().all()
    nodes = {c.id: _cat_out(c) for c in cats}
    roots: list[CategoryOut] = []
    for c in cats:
        node = nodes[c.id]
        if c.parent_id and c.parent_id in nodes:
            nodes[c.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


@router.post("/categories", response_model=CategoryOut, status_code=201)
async def create_category(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    data = payload.model_dump()
    if data.get("parent_id"):
        parent = (await db.execute(select(Category).where(Category.id == data["parent_id"]))).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=400, detail="Родительская категория не найдена")
    data["slug"] = await _unique_category_slug(db, data.get("slug") or data["name"])
    cat = Category(**data)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    from app.services.cache_service import invalidate_prefix
    await invalidate_prefix("categories:")
    return _cat_out(cat)


async def _is_descendant(db: AsyncSession, candidate_parent_id: int, cat_id: int) -> bool:
    """True if candidate_parent_id is `cat_id` itself or one of its descendants
    (moving a category under its own subtree would create a cycle)."""
    current = candidate_parent_id
    seen = set()
    while current is not None and current not in seen:
        if current == cat_id:
            return True
        seen.add(current)
        current = (await db.execute(
            select(Category.parent_id).where(Category.id == current)
        )).scalar_one_or_none()
    return False


@router.put("/categories/{cat_id}", response_model=CategoryOut)
async def update_category(
    cat_id: int,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    cat = (await db.execute(select(Category).where(Category.id == cat_id))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    data = payload.model_dump(exclude_unset=True)

    # Moving the category: validate the new parent and prevent cycles.
    if "parent_id" in data and data["parent_id"] != cat.parent_id:
        new_parent = data["parent_id"]
        if new_parent is not None:
            if new_parent == cat_id or await _is_descendant(db, new_parent, cat_id):
                raise HTTPException(status_code=400, detail="Нельзя переместить категорию внутрь самой себя")
            if (await db.execute(select(Category.id).where(Category.id == new_parent))).scalar_one_or_none() is None:
                raise HTTPException(status_code=400, detail="Родительская категория не найдена")

    if "slug" in data or "name" in data:
        base = data.get("slug") or data.get("name") or cat.name
        data["slug"] = await _unique_category_slug(db, base, exclude_id=cat_id)

    for field, value in data.items():
        setattr(cat, field, value)
    await db.commit()
    await db.refresh(cat)
    from app.services.cache_service import invalidate_prefix
    await invalidate_prefix("categories:")
    return _cat_out(cat)


@router.delete("/categories/{cat_id}", status_code=204)
async def delete_category(
    cat_id: int,
    reassign_to: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """
    Delete a category. Refuses if it still has subcategories. If it has products,
    pass ?reassign_to=<other_category_id> to move them first; otherwise the
    deletion is refused so products are never orphaned.
    """
    from app.models.models import Product
    cat = (await db.execute(select(Category).where(Category.id == cat_id))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    child_count = (await db.execute(
        select(func.count()).select_from(Category).where(Category.parent_id == cat_id)
    )).scalar_one()
    if child_count:
        raise HTTPException(status_code=400, detail="Сначала удалите или перенесите подкатегории")

    product_count = (await db.execute(
        select(func.count()).select_from(Product).where(Product.category_id == cat_id)
    )).scalar_one()
    if product_count:
        if reassign_to is None:
            raise HTTPException(
                status_code=400,
                detail=f"В категории {product_count} тов. Передайте reassign_to для переноса перед удалением.",
            )
        target = (await db.execute(select(Category).where(Category.id == reassign_to))).scalar_one_or_none()
        if not target or reassign_to == cat_id:
            raise HTTPException(status_code=400, detail="Неверная категория для переноса")
        await db.execute(
            update(Product).where(Product.category_id == cat_id).values(category_id=reassign_to)
        )

    await db.delete(cat)
    await db.commit()
    from app.services.cache_service import invalidate_prefix
    await invalidate_prefix("categories:")


# ─── Reports ──────────────────────────────────────────────────────────────────

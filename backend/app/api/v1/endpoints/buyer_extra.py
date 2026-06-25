"""
Block 2 endpoints: address book, wishlist collections, and browsing history.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.models import (
    Address, Product, ProductStatus, ProductView, User,
    WishlistCollection, WishlistItem,
)
from app.schemas.schemas import (
    AddressCreate, AddressOut, ProductListOut,
    WishlistCollectionBrief, WishlistCollectionCreate, WishlistCollectionOut,
)

router = APIRouter(tags=["buyer-extra"])


# ─── Address book ────────────────────────────────────────────────────────────────

@router.get("/addresses", response_model=list[AddressOut])
async def list_addresses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Address).where(Address.user_id == current_user.id)
        .order_by(Address.is_default.desc(), Address.created_at.desc())
    )
    return result.scalars().all()


@router.post("/addresses", response_model=AddressOut, status_code=201)
async def create_address(
    payload: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # If this is the user's first address, force it default. If marked default,
    # clear the flag on all the others so exactly one stays default.
    existing_count = (await db.execute(
        select(func.count()).select_from(Address).where(Address.user_id == current_user.id)
    )).scalar_one()
    make_default = payload.is_default or existing_count == 0

    if make_default:
        await db.execute(
            update(Address).where(Address.user_id == current_user.id).values(is_default=False)
        )

    addr = Address(user_id=current_user.id, **{**payload.model_dump(), "is_default": make_default})
    db.add(addr)
    await db.commit()
    await db.refresh(addr)
    return addr


@router.put("/addresses/{address_id}", response_model=AddressOut)
async def update_address(
    address_id: int,
    payload: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    addr = (await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == current_user.id)
    )).scalar_one_or_none()
    if not addr:
        raise HTTPException(status_code=404, detail="Адрес не найден")
    if payload.is_default:
        await db.execute(
            update(Address).where(Address.user_id == current_user.id).values(is_default=False)
        )
    for field, value in payload.model_dump().items():
        setattr(addr, field, value)
    await db.commit()
    await db.refresh(addr)
    return addr


@router.delete("/addresses/{address_id}", status_code=204)
async def delete_address(
    address_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    addr = (await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == current_user.id)
    )).scalar_one_or_none()
    if not addr:
        raise HTTPException(status_code=404, detail="Адрес не найден")
    was_default = addr.is_default
    await db.delete(addr)
    await db.flush()
    # If we removed the default, promote the most recent remaining address.
    if was_default:
        nxt = (await db.execute(
            select(Address).where(Address.user_id == current_user.id)
            .order_by(Address.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if nxt:
            nxt.is_default = True
    await db.commit()


# ─── Wishlist collections ────────────────────────────────────────────────────────

@router.get("/wishlists", response_model=list[WishlistCollectionBrief])
async def list_wishlists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cols = (await db.execute(
        select(WishlistCollection).where(WishlistCollection.user_id == current_user.id)
        .order_by(WishlistCollection.created_at)
    )).scalars().all()
    out = []
    for c in cols:
        count = (await db.execute(
            select(func.count()).select_from(WishlistItem).where(WishlistItem.collection_id == c.id)
        )).scalar_one()
        brief = WishlistCollectionBrief.model_validate(c)
        brief.item_count = count
        out.append(brief)
    return out


@router.post("/wishlists", response_model=WishlistCollectionBrief, status_code=201)
async def create_wishlist(
    payload: WishlistCollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    col = WishlistCollection(user_id=current_user.id, **payload.model_dump())
    db.add(col)
    await db.commit()
    await db.refresh(col)
    brief = WishlistCollectionBrief.model_validate(col)
    brief.item_count = 0
    return brief


@router.get("/wishlists/{collection_id}", response_model=WishlistCollectionOut)
async def get_wishlist(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    col = (await db.execute(
        select(WishlistCollection)
        .options(
            selectinload(WishlistCollection.items)
            .selectinload(WishlistItem.product)
            .selectinload(Product.images)
        )
        .where(WishlistCollection.id == collection_id)
    )).scalar_one_or_none()
    if not col or (col.user_id != current_user.id and not col.is_public):
        raise HTTPException(status_code=404, detail="Коллекция не найдена")
    return col


@router.delete("/wishlists/{collection_id}", status_code=204)
async def delete_wishlist(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    col = (await db.execute(
        select(WishlistCollection).where(
            WishlistCollection.id == collection_id,
            WishlistCollection.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Коллекция не найдена")
    await db.delete(col)
    await db.commit()


@router.post("/wishlists/{collection_id}/items/{product_id}", status_code=201)
async def add_to_wishlist(
    collection_id: int,
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    col = (await db.execute(
        select(WishlistCollection).where(
            WishlistCollection.id == collection_id,
            WishlistCollection.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Коллекция не найдена")
    # Idempotent: ignore if already present
    existing = (await db.execute(
        select(WishlistItem).where(
            WishlistItem.collection_id == collection_id,
            WishlistItem.product_id == product_id,
        )
    )).scalar_one_or_none()
    if existing:
        return {"status": "already_present"}
    db.add(WishlistItem(collection_id=collection_id, product_id=product_id))
    await db.commit()
    return {"status": "added"}


@router.delete("/wishlists/{collection_id}/items/{product_id}", status_code=204)
async def remove_from_wishlist(
    collection_id: int,
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (await db.execute(
        select(WishlistItem)
        .join(WishlistCollection, WishlistCollection.id == WishlistItem.collection_id)
        .where(
            WishlistItem.collection_id == collection_id,
            WishlistItem.product_id == product_id,
            WishlistCollection.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Товар не найден в коллекции")
    await db.delete(item)
    await db.commit()


# ─── Browsing history ────────────────────────────────────────────────────────────

@router.get("/recently-viewed", response_model=list[ProductListOut])
async def recently_viewed(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The user's most recently viewed active products (max 12)."""
    rows = (await db.execute(
        select(ProductView.product_id)
        .where(ProductView.user_id == current_user.id)
        .order_by(ProductView.viewed_at.desc())
        .limit(12)
    )).scalars().all()
    if not rows:
        return []
    products = (await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id.in_(rows), Product.status == ProductStatus.active)
    )).scalars().all()
    # Preserve recency order
    by_id = {p.id: p for p in products}
    return [ProductListOut.model_validate(by_id[pid]) for pid in rows if pid in by_id]

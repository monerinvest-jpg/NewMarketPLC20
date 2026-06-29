"""
Product CRUD endpoints (seller + public).
"""
from typing import Optional
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_seller, get_current_user, get_current_user_optional
from app.core.config import settings
from app.core.database import get_db
from app.models.models import (
    Category, DigitalAsset, Product, ProductImage, ProductStatus, ProductType, Shop, User,
)
from app.schemas.schemas import DigitalAssetOut, ProductCreate, ProductOut, ProductUpdate
from app.services.settings_service import is_premoderation_enabled

router = APIRouter(prefix="/products", tags=["products"])


async def _get_seller_shop(user: User, db: AsyncSession) -> Shop:
    result = await db.execute(select(Shop).where(Shop.owner_id == user.id))
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="You don't have a shop yet")
    return shop


@router.get("", response_model=dict)
async def list_products(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    q: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    attrs: Optional[str] = None,
    sort: Optional[str] = Query("created_at_desc", pattern="^(price_asc|price_desc|rating_desc|created_at_desc|views_desc)$"),
):
    """Public product catalog with search, filters, pagination."""
    query = (
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.status == ProductStatus.active)
    )

    if category_id:
        query = query.where(Product.category_id == category_id)
    if q:
        query = query.where(
            or_(
                Product.title.ilike(f"%{q}%"),
                Product.description.ilike(f"%{q}%"),
            )
        )
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    if min_rating is not None:
        query = query.where(Product.rating >= min_rating)

    # Faceted attribute filters: attrs="3:Red,5:Cotton" → product must have a
    # matching value for each requested attribute (AND across attributes).
    if attrs:
        from app.models.models import ProductAttributeValue
        for pair in attrs.split(","):
            if ":" not in pair:
                continue
            attr_id_str, value = pair.split(":", 1)
            try:
                attr_id = int(attr_id_str)
            except ValueError:
                continue
            sub = (
                select(ProductAttributeValue.product_id)
                .where(
                    ProductAttributeValue.attribute_id == attr_id,
                    ProductAttributeValue.value == value,
                )
            )
            query = query.where(Product.id.in_(sub))

    # Sorting
    sort_map = {
        "price_asc": Product.price.asc(),
        "price_desc": Product.price.desc(),
        "rating_desc": Product.rating.desc(),
        "created_at_desc": Product.created_at.desc(),
        "views_desc": Product.views_count.desc(),
    }
    query = query.order_by(sort_map.get(sort, Product.created_at.desc()))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    products = result.scalars().all()

    return {
        "items": [ProductOut.model_validate(p) for p in products],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.get("/search", response_model=dict)
async def search_products_endpoint(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Full-text product search. Uses MeiliSearch when configured, otherwise falls
    back to a database ILIKE search. Returns the same shape as the catalog list.
    """
    from app.services.search_service import search_products
    from app.schemas.schemas import ProductListOut
    result = await search_products(db, q, limit=page_size, offset=(page - 1) * page_size)
    items = result["items"]
    # DB engine returns ORM objects; meili returns dicts already
    serialized = [
        ProductListOut.model_validate(p) if not isinstance(p, dict) else p
        for p in items
    ]
    return {
        "items": serialized,
        "total": result["total"],
        "page": page,
        "page_size": page_size,
        "engine": result["engine"],
    }


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id == product_id, Product.status == ProductStatus.active)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Increment view counter
    await db.execute(
        update(Product).where(Product.id == product_id).values(views_count=Product.views_count + 1)
    )

    # Record browsing history for logged-in users (upsert: refresh viewed_at)
    if current_user is not None:
        from datetime import datetime, timezone
        from app.models.models import ProductView
        existing = (await db.execute(
            select(ProductView).where(
                ProductView.user_id == current_user.id,
                ProductView.product_id == product_id,
            )
        )).scalar_one_or_none()
        if existing:
            existing.viewed_at = datetime.now(timezone.utc)
        else:
            db.add(ProductView(user_id=current_user.id, product_id=product_id))

    await db.commit()

    # Attach running flash-sale price for display
    from app.services.stock_service import get_running_flash_sale, effective_price
    from app.schemas.schemas import ProductOut
    sale = await get_running_flash_sale(db, product_id)
    out = ProductOut.model_validate(product)
    if sale:
        out.flash_price = effective_price(product.price, sale.discount_percent)
        out.flash_discount_percent = sale.discount_percent
        out.flash_ends_at = sale.ends_at
    return out


# ─── Seller endpoints ─────────────────────────────────────────────────────────

@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_seller_shop(current_user, db)

    # Determine initial status based on premoderation setting
    premod = await is_premoderation_enabled(db)
    initial_status = ProductStatus.pending if premod else ProductStatus.active

    # Digital/course products have unlimited stock — quantity/weight are ignored.
    is_physical = payload.product_type == ProductType.physical
    product = Product(
        shop_id=shop.id,
        category_id=payload.category_id,
        title=payload.title,
        description=payload.description,
        price=payload.price,
        compare_at_price=payload.compare_at_price,
        quantity=payload.quantity if is_physical else 0,
        weight_g=payload.weight_g if is_physical else 0,
        product_type=payload.product_type,
        status=initial_status,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    # Generate SEO slug now that we have the id (slug = transliterated title + id)
    from app.services.slug_service import product_slug
    product.slug = product_slug(product.title, product.id)
    await db.commit()
    await db.refresh(product)

    # Notify followers of the shop when a product goes live immediately.
    if product.status == ProductStatus.active:
        from app.services import shop_follow_service
        await shop_follow_service.notify_followers(
            db, shop.id,
            title=f"Новинка в магазине «{shop.name}»",
            body=product.title,
            link=f"/products/{product.id}",
        )
        await db.commit()
    return product


@router.put("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_seller_shop(current_user, db)
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_seller_shop(current_user, db)
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.commit()


@router.post("/{product_id}/images", status_code=status.HTTP_201_CREATED)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    is_main: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_seller_shop(current_user, db)
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"
    upload_path = os.path.join(settings.UPLOAD_DIR, "products")
    os.makedirs(upload_path, exist_ok=True)
    full_path = os.path.join(upload_path, filename)

    contents = await file.read()
    with open(full_path, "wb") as f:
        f.write(contents)

    if is_main:
        # Unset other main images
        await db.execute(
            update(ProductImage)
            .where(ProductImage.product_id == product_id)
            .values(is_main=False)
        )

    image = ProductImage(
        product_id=product_id,
        url=f"/uploads/products/{filename}",
        is_main=is_main,
    )
    db.add(image)
    await db.commit()
    return {"url": image.url}


# ─── Digital assets (seller) ──────────────────────────────────────────────────

@router.get("/{product_id}/digital-assets", response_model=list[DigitalAssetOut])
async def list_digital_assets(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """List the digital files attached to the seller's own product."""
    shop = await _get_seller_shop(current_user, db)
    product = (await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop.id)
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    assets = (await db.execute(
        select(DigitalAsset).where(DigitalAsset.product_id == product_id)
        .order_by(DigitalAsset.sort_order, DigitalAsset.id)
    )).scalars().all()
    return assets


@router.post("/{product_id}/digital-assets", response_model=DigitalAssetOut, status_code=status.HTTP_201_CREATED)
async def upload_digital_asset(
    product_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """
    Attach a downloadable file to a digital/course product. Stored privately;
    buyers receive it only via an entitlement-checked download.
    """
    from app.services import digital_storage_service

    shop = await _get_seller_shop(current_user, db)
    product = (await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop.id)
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.product_type == ProductType.physical:
        raise HTTPException(status_code=400, detail="Файлы можно прикладывать только к цифровым товарам или курсам")

    content = await file.read()
    try:
        storage_key, size = await digital_storage_service.save_digital_asset(
            content, file.content_type or "application/octet-stream", file.filename or "file",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    next_order = (await db.execute(
        select(func.coalesce(func.max(DigitalAsset.sort_order), -1)).where(DigitalAsset.product_id == product_id)
    )).scalar_one() + 1
    asset = DigitalAsset(
        product_id=product_id,
        file_name=file.filename or "file",
        storage_key=storage_key,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size,
        sort_order=next_order,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


@router.delete("/{product_id}/digital-assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_digital_asset(
    product_id: int,
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Remove a digital file from the seller's product (also deletes the stored file)."""
    from app.services import digital_storage_service

    shop = await _get_seller_shop(current_user, db)
    asset = (await db.execute(
        select(DigitalAsset)
        .join(Product, Product.id == DigitalAsset.product_id)
        .where(DigitalAsset.id == asset_id, DigitalAsset.product_id == product_id, Product.shop_id == shop.id)
    )).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="File not found")
    key = asset.storage_key
    await db.delete(asset)
    await db.commit()
    digital_storage_service.delete_digital_asset(key)


@router.get("/seller/my", response_model=dict)
async def get_my_products(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = None,
):
    shop = await _get_seller_shop(current_user, db)
    query = select(Product).options(selectinload(Product.images)).where(Product.shop_id == shop.id)
    if status_filter:
        query = query.where(Product.status == status_filter)
    query = query.order_by(Product.created_at.desc())

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    products = result.scalars().all()

    return {
        "items": [ProductOut.model_validate(p) for p in products],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.post("/import-csv")
async def import_products_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_seller),
):
    """
    Bulk-import products from a CSV for the current seller's shop.
    Expected columns: title, description, price, quantity, category_id,
    weight_g (optional), compare_at_price (optional).
    Returns a per-row summary.
    """
    import csv
    import io
    from decimal import Decimal, InvalidOperation
    from app.models.models import Product, Shop, ProductStatus, Category
    from app.services.slug_service import product_slug
    from app.services.settings_service import get_setting

    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    premod = (await get_setting(db, "enable_premoderation")).lower() == "true"
    initial_status = ProductStatus.pending if premod else ProductStatus.active

    valid_categories = {c.id for c in (await db.execute(select(Category))).scalars().all()}

    created, errors = 0, []
    for i, row in enumerate(reader, start=2):  # row 1 is header
        try:
            title = (row.get("title") or "").strip()
            if not title:
                errors.append(f"Строка {i}: пустое название")
                continue
            cat_id = int(row.get("category_id") or 0)
            if cat_id not in valid_categories:
                errors.append(f"Строка {i}: неверная категория {cat_id}")
                continue
            price = Decimal(str(row.get("price") or "0"))
            quantity = int(row.get("quantity") or 0)
            product = Product(
                shop_id=shop.id,
                category_id=cat_id,
                title=title,
                description=(row.get("description") or "").strip() or None,
                price=price,
                compare_at_price=Decimal(row["compare_at_price"]) if row.get("compare_at_price") else None,
                quantity=quantity,
                weight_g=int(row.get("weight_g") or 500),
                status=initial_status,
            )
            db.add(product)
            await db.flush()
            product.slug = product_slug(product.title, product.id)
            created += 1
        except (ValueError, InvalidOperation) as e:
            errors.append(f"Строка {i}: ошибка данных ({e})")
        except Exception as e:
            errors.append(f"Строка {i}: {e}")

    await db.commit()
    return {"created": created, "errors": errors, "total_rows": created + len(errors)}

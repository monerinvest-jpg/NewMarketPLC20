"""
Block 3 endpoints: stock movements & low-stock, flash sales, bulk edit,
and CSV export — all scoped to the current seller's shop.
"""
import csv
import io
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_seller
from app.core.database import get_db
from app.models.models import (
    FlashSale, Product, ProductStatus, Shop, StockMovement, User,
)
from app.schemas.schemas import (
    BulkPriceUpdate, BulkStatusUpdate, FlashSaleCreate, FlashSaleOut,
    FlashSaleWithProduct, LowStockItem, StockAdjustRequest, StockMovementOut,
)
from app.services.stock_service import record_movement, effective_price

router = APIRouter(prefix="/seller", tags=["seller-inventory"])

LOW_STOCK_THRESHOLD = 5


async def _get_shop(db: AsyncSession, user: User) -> Shop:
    shop = (await db.execute(select(Shop).where(Shop.owner_id == user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="У вас нет магазина")
    return shop


async def _owns_product(db: AsyncSession, shop_id: int, product_id: int) -> Product:
    product = (await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop_id)
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден в вашем магазине")
    return product


# ─── Stock ───────────────────────────────────────────────────────────────────────

@router.post("/stock/adjust", response_model=StockMovementOut)
async def adjust_stock(
    payload: StockAdjustRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Manually add or remove stock; records a movement with reason 'manual'."""
    shop = await _get_shop(db, current_user)
    await _owns_product(db, shop.id, payload.product_id)
    movement = await record_movement(
        db, payload.product_id, payload.change, "manual",
        variant_id=payload.variant_id, note=payload.note,
    )
    await db.commit()
    await db.refresh(movement)
    return movement


@router.get("/stock/movements", response_model=list[StockMovementOut])
async def stock_movements(
    product_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """History of stock movements for one of the seller's products."""
    shop = await _get_shop(db, current_user)
    await _owns_product(db, shop.id, product_id)
    rows = (await db.execute(
        select(StockMovement).where(StockMovement.product_id == product_id)
        .order_by(StockMovement.created_at.desc()).limit(100)
    )).scalars().all()
    return rows


@router.get("/stock/low", response_model=list[LowStockItem])
async def low_stock(
    threshold: int = Query(LOW_STOCK_THRESHOLD, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Products at or below the low-stock threshold."""
    shop = await _get_shop(db, current_user)
    rows = (await db.execute(
        select(Product).where(
            Product.shop_id == shop.id,
            Product.quantity <= threshold,
            Product.status == ProductStatus.active,
        ).order_by(Product.quantity)
    )).scalars().all()
    return [
        LowStockItem(product_id=p.id, title=p.title, quantity=p.quantity, threshold=threshold)
        for p in rows
    ]


# ─── Flash sales ──────────────────────────────────────────────────────────────────

@router.get("/flash-sales", response_model=list[FlashSaleWithProduct])
async def list_flash_sales(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_shop(db, current_user)
    sales = (await db.execute(
        select(FlashSale).where(FlashSale.shop_id == shop.id).order_by(FlashSale.starts_at.desc())
    )).scalars().all()
    now = datetime.now(timezone.utc)
    out = []
    for s in sales:
        product = (await db.execute(select(Product).where(Product.id == s.product_id))).scalar_one_or_none()
        item = FlashSaleWithProduct.model_validate(s)
        if product:
            item.product_title = product.title
            item.base_price = product.price
            item.effective_price = effective_price(product.price, s.discount_percent)
        item.is_running = bool(s.is_active and s.starts_at <= now <= s.ends_at)
        out.append(item)
    return out


@router.post("/flash-sales", response_model=FlashSaleOut, status_code=201)
async def create_flash_sale(
    payload: FlashSaleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_shop(db, current_user)
    await _owns_product(db, shop.id, payload.product_id)
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=400, detail="Дата окончания должна быть позже начала")
    sale = FlashSale(
        product_id=payload.product_id,
        shop_id=shop.id,
        discount_percent=payload.discount_percent,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=True,
    )
    db.add(sale)
    await db.commit()
    await db.refresh(sale)

    # Notify shop followers about the new flash sale.
    from app.services import shop_follow_service
    from app.models.models import Product as _Product
    prod = (await db.execute(select(_Product).where(_Product.id == payload.product_id))).scalar_one_or_none()
    await shop_follow_service.notify_followers(
        db, shop.id,
        title=f"🔥 Распродажа в «{shop.name}»",
        body=f"−{int(payload.discount_percent)}% на {prod.title if prod else 'товар'}",
        link=f"/products/{payload.product_id}",
    )
    await db.commit()
    return sale


@router.delete("/flash-sales/{sale_id}", status_code=204)
async def delete_flash_sale(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_shop(db, current_user)
    sale = (await db.execute(
        select(FlashSale).where(FlashSale.id == sale_id, FlashSale.shop_id == shop.id)
    )).scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Акция не найдена")
    await db.delete(sale)
    await db.commit()


# ─── Bulk operations ──────────────────────────────────────────────────────────────

@router.post("/products/bulk-price")
async def bulk_price(
    payload: BulkPriceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Set an absolute price or apply a percentage change to many products."""
    if payload.set_price is None and payload.change_percent is None:
        raise HTTPException(status_code=400, detail="Укажите set_price или change_percent")
    shop = await _get_shop(db, current_user)
    products = (await db.execute(
        select(Product).where(Product.id.in_(payload.product_ids), Product.shop_id == shop.id)
    )).scalars().all()
    updated = 0
    for p in products:
        if payload.set_price is not None:
            p.price = payload.set_price
        else:
            factor = (Decimal("100") + payload.change_percent) / Decimal("100")
            p.price = (p.price * factor).quantize(Decimal("0.01"))
            if p.price < 0:
                p.price = Decimal("0.00")
        updated += 1
    await db.commit()
    return {"updated": updated}


@router.post("/products/bulk-status")
async def bulk_status(
    payload: BulkStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Activate/deactivate many products at once (active <-> blocked)."""
    shop = await _get_shop(db, current_user)
    products = (await db.execute(
        select(Product).where(Product.id.in_(payload.product_ids), Product.shop_id == shop.id)
    )).scalars().all()
    new_status = ProductStatus.active if payload.is_active else ProductStatus.blocked
    for p in products:
        p.status = new_status
    await db.commit()
    return {"updated": len(products)}


@router.get("/products/export-csv")
async def export_products_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Export all of the seller's products as a CSV download."""
    shop = await _get_shop(db, current_user)
    products = (await db.execute(
        select(Product).where(Product.shop_id == shop.id).order_by(Product.id)
    )).scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "title", "description", "price", "compare_at_price",
                     "quantity", "weight_g", "category_id", "status"])
    for p in products:
        writer.writerow([
            p.id, p.title, p.description or "", p.price, p.compare_at_price or "",
            p.quantity, p.weight_g, p.category_id, p.status.value,
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )

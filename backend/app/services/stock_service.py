"""
Stock service. Central helper to adjust a product's (or variant's) stock while
recording an auditable StockMovement, plus effective-price resolution that
accounts for any running flash sale.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import FlashSale, Product, ProductVariant, StockMovement


async def record_movement(
    db: AsyncSession,
    product_id: int,
    change: int,
    reason: str,
    variant_id: Optional[int] = None,
    note: Optional[str] = None,
    apply_to_stock: bool = True,
) -> StockMovement:
    """
    Adjust stock and append a StockMovement. When apply_to_stock is True the
    product/variant quantity is mutated by `change`; pass False to only log a
    movement whose quantity change was already applied elsewhere (e.g. checkout).
    Caller commits.
    """
    quantity_after = 0
    if variant_id is not None:
        variant = (await db.execute(
            select(ProductVariant).where(ProductVariant.id == variant_id)
        )).scalar_one_or_none()
        if variant:
            if apply_to_stock:
                variant.quantity += change
            quantity_after = variant.quantity
    else:
        product = (await db.execute(
            select(Product).where(Product.id == product_id)
        )).scalar_one_or_none()
        if product:
            if apply_to_stock:
                product.quantity += change
            quantity_after = product.quantity

    movement = StockMovement(
        product_id=product_id,
        variant_id=variant_id,
        change=change,
        reason=reason,
        quantity_after=quantity_after,
        note=note,
    )
    db.add(movement)
    return movement


async def get_running_flash_sale(db: AsyncSession, product_id: int) -> Optional[FlashSale]:
    """Return the currently active flash sale for a product, if any."""
    now = datetime.now(timezone.utc)
    return (await db.execute(
        select(FlashSale).where(
            FlashSale.product_id == product_id,
            FlashSale.is_active == True,  # noqa: E712
            FlashSale.starts_at <= now,
            FlashSale.ends_at >= now,
        ).order_by(FlashSale.discount_percent.desc()).limit(1)
    )).scalar_one_or_none()


def effective_price(base_price: Decimal, discount_percent: Decimal) -> Decimal:
    """Compute the discounted price, rounded to kopecks."""
    discounted = base_price * (Decimal("100") - discount_percent) / Decimal("100")
    return discounted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

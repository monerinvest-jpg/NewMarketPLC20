"""
Shopping cart endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.models import CartItem, Product, ProductStatus, User
from app.schemas.schemas import CartItemCreate, CartItemOut, CartItemUpdate, CartPromoSummary
from app.services import promo_rules_service, stock_service

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("/summary", response_model=CartPromoSummary)
async def cart_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cart subtotal and the automatic promotion discount (rules + bundles)."""
    from decimal import Decimal
    items = (await db.execute(
        select(CartItem).options(selectinload(CartItem.product))
        .where(CartItem.user_id == current_user.id)
    )).scalars().all()

    lines, subtotal = [], Decimal("0.00")
    for it in items:
        if it.product is None or it.product.status != ProductStatus.active:
            continue
        sale = await stock_service.get_running_flash_sale(db, it.product_id)
        unit = stock_service.effective_price(it.product.price, sale.discount_percent) if sale else it.product.price
        subtotal += unit * it.quantity
        lines.append({"product": it.product, "quantity": it.quantity, "unit_price": unit})

    promo = await promo_rules_service.compute_promotions(db, lines)
    discount = promo["discount"]
    return CartPromoSummary(
        subtotal=subtotal.quantize(Decimal("0.01")),
        promo_discount=discount,
        breakdown=promo["breakdown"],
        estimated_total=max(Decimal("0.00"), (subtotal - discount)).quantize(Decimal("0.01")),
    )


@router.get("", response_model=list[CartItemOut])
async def get_cart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CartItem)
        .options(selectinload(CartItem.product).selectinload(Product.images), selectinload(CartItem.variant))
        .where(CartItem.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("", response_model=CartItemOut, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    payload: CartItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prod_result = await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id == payload.product_id, Product.status == ProductStatus.active)
    )
    product = prod_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or unavailable")

    # If a variant is specified, validate it belongs to the product and has stock
    from app.models.models import ProductVariant
    variant = None
    if payload.variant_id is not None:
        v_result = await db.execute(
            select(ProductVariant).where(
                ProductVariant.id == payload.variant_id,
                ProductVariant.product_id == product.id,
                ProductVariant.is_active == True,  # noqa: E712
            )
        )
        variant = v_result.scalar_one_or_none()
        if not variant:
            raise HTTPException(status_code=404, detail="Вариант товара не найден")
        if variant.quantity < payload.quantity:
            raise HTTPException(status_code=400, detail="Недостаточно товара выбранного варианта")
    else:
        if product.quantity < payload.quantity:
            raise HTTPException(status_code=400, detail="Not enough stock")

    existing_result = await db.execute(
        select(CartItem).where(
            CartItem.user_id == current_user.id,
            CartItem.product_id == payload.product_id,
            CartItem.variant_id == payload.variant_id,
        )
    )
    cart_item = existing_result.scalar_one_or_none()

    if cart_item:
        cart_item.quantity += payload.quantity
    else:
        cart_item = CartItem(
            user_id=current_user.id,
            product_id=payload.product_id,
            variant_id=payload.variant_id,
            quantity=payload.quantity,
        )
        db.add(cart_item)

    await db.commit()
    await db.refresh(cart_item)
    await db.refresh(cart_item, ["product", "variant"])
    return cart_item


@router.patch("/{item_id}", response_model=CartItemOut)
async def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CartItem)
        .options(selectinload(CartItem.product).selectinload(Product.images), selectinload(CartItem.variant))
        .where(CartItem.id == item_id, CartItem.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    if item.product.quantity < payload.quantity:
        raise HTTPException(status_code=400, detail="Not enough stock")
    item.quantity = payload.quantity
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_cart(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    await db.delete(item)
    await db.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CartItem).where(CartItem.user_id == current_user.id))
    for item in result.scalars().all():
        await db.delete(item)
    await db.commit()

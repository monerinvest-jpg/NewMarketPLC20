"""
Orders: creation, status updates, payment initiation, webhook handling.
"""
import json
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_seller, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.models import (
    CartItem, Coupon, DeliveryInfo, FiscalReceipt, FiscalReceiptType, Order, OrderItem,
    OrderStatus, Payment, PaymentGateway, PaymentStatus, Product, ProductStatus, ProductType,
    Shop, User, BalanceTransaction, BalanceTransactionType,
)
from app.schemas.schemas import FiscalReceiptOut, OrderCreate, OrderOut, OrderStatusUpdate
from app.services import fiscal_service
from app.services import promo_rules_service
from app.services import gift_service
from app.services.commission_service import calculate_item_financials, get_effective_commission
from app.services.delivery_service import get_delivery_gateway
from app.services.payment_service import get_payment_gateway
from app.services.payout_service import payout_sellers_for_order
from app.services.referral_service import process_buyer_referral_reward, process_seller_referral_reward
from app.services.settings_service import get_referral_settings

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create order from cart. Calculates delivery, applies coupon/bonus,
    computes commission, creates YooKassa payment.
    """
    # 1. Load cart
    cart_result = await db.execute(
        select(CartItem)
        .options(
            selectinload(CartItem.product).selectinload(Product.shop),
            selectinload(CartItem.variant),
        )
        .where(CartItem.user_id == current_user.id)
    )
    cart_items = cart_result.scalars().all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # 2. Validate products and compute subtotal
    subtotal = Decimal("0")
    order_items_data = []
    shops = {}
    for item in cart_items:
        product = item.product
        variant = item.variant
        if product.status != ProductStatus.active:
            raise HTTPException(status_code=400, detail=f"Product '{product.title}' is not available")

        # Digital/course products have unlimited stock — only physical goods are
        # stock-checked. When the line references a variant, its own price and
        # stock take precedence over the product's base price/quantity.
        is_phys = product.product_type == ProductType.physical
        if variant is not None:
            if is_phys and variant.quantity < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Недостаточно товара варианта '{variant.name}': запрошено {item.quantity}, в наличии {variant.quantity}",
                )
            unit_price = variant.price if variant.price is not None else product.price
        else:
            if is_phys and product.quantity < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough stock for '{product.title}': requested {item.quantity}, available {product.quantity}",
                )
            unit_price = product.price

        line_total = unit_price * item.quantity
        subtotal += line_total
        order_items_data.append({
            "product": product,
            "variant": variant,
            "quantity": item.quantity,
            "price_at_time": unit_price,
        })
        shops[product.shop_id] = product.shop

    # 3. Get effective commission for each shop represented in the cart.
    # An order can span multiple shops; each shop's commission is looked up
    # independently rather than assuming the whole order uses one rate.
    commission_by_shop: dict[int, Decimal] = {}
    for shop_id, shop in shops.items():
        commission_by_shop[shop_id] = await get_effective_commission(db, shop)

    # 4. Calculate delivery cost. Digital/course-only orders never ship, so
    # delivery is skipped entirely (cost 0, no DeliveryInfo).
    has_physical = any(
        d["product"].product_type == ProductType.physical for d in order_items_data
    )
    delivery_cost = Decimal("0.00")
    rate = None
    if has_physical:
        delivery_gw = get_delivery_gateway(payload.delivery_service)
        total_weight = sum(
            item["product"].weight_g * item["quantity"] for item in order_items_data
        )
        rate = await delivery_gw.calculate_rate("Москва", payload.city_to, total_weight)
        delivery_cost = rate.cost

        # Loyalty perk: free shipping for eligible tiers.
        from app.services import loyalty_tier_service
        if await loyalty_tier_service.has_free_shipping(db, current_user):
            delivery_cost = Decimal("0.00")

    # 5. Validate and apply coupon
    coupon_discount = Decimal("0")
    coupon_obj = None
    if payload.coupon_code:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        coupon_result = await db.execute(
            select(Coupon).where(
                Coupon.code == payload.coupon_code,
                Coupon.is_active == True,
                Coupon.valid_from <= now,
                Coupon.valid_until >= now,
            )
        )
        coupon_obj = coupon_result.scalar_one_or_none()
        if not coupon_obj:
            raise HTTPException(status_code=400, detail="Invalid or expired coupon code")
        if coupon_obj.max_uses > 0 and coupon_obj.used_count >= coupon_obj.max_uses:
            raise HTTPException(status_code=400, detail="Coupon usage limit reached")
        if subtotal < coupon_obj.min_order_amount:
            raise HTTPException(
                status_code=400,
                detail=f"Minimum order amount for this coupon is {coupon_obj.min_order_amount} ₽",
            )
        if coupon_obj.discount_type.value == "percent":
            coupon_discount = (subtotal * coupon_obj.discount_value / 100).quantize(Decimal("0.01"))
        else:
            coupon_discount = min(coupon_obj.discount_value, subtotal)
        coupon_obj.used_count += 1

    # 6. Validate and apply bonus
    ref_settings = await get_referral_settings(db)
    max_bonus_pct = ref_settings["referral_bonus_max_discount_percent"]
    max_bonus_allowed = (subtotal * max_bonus_pct / 100).quantize(Decimal("0.01"))
    bonus_to_use = min(payload.bonus_to_use, max_bonus_allowed, current_user.bonus_balance)

    # 7. Per-item financials: each item's platform_fee/seller_net is calculated
    # using its own shop's commission rate. Order-level platform_fee/seller_net
    # are then the sums across items (used for display; payouts always read
    # from OrderItem, never from these aggregates).
    item_financials = []
    total_platform_fee = Decimal("0.00")
    total_seller_net = Decimal("0.00")
    for item_data in order_items_data:
        line_subtotal = item_data["price_at_time"] * item_data["quantity"]
        shop_commission = commission_by_shop[item_data["product"].shop_id]
        fin = calculate_item_financials(line_subtotal, shop_commission)
        item_financials.append({**item_data, **fin, "commission_percent_used": shop_commission})
        total_platform_fee += fin["platform_fee"]
        total_seller_net += fin["seller_net"]

    # Blended commission rate for display purposes only (weighted by subtotal)
    blended_commission_percent = (
        (total_platform_fee / subtotal * Decimal("100")).quantize(Decimal("0.01"))
        if subtotal > 0 else Decimal("0.00")
    )

    # Automatic promotions (nplus / volume rules + bundles). Computed from the
    # cart lines and added to the discount stack like a coupon.
    promo_lines = [
        {"product": d["product"], "quantity": d["quantity"], "unit_price": d["price_at_time"]}
        for d in order_items_data
    ]
    promo_result = await promo_rules_service.compute_promotions(db, promo_lines)
    promo_discount = promo_result["discount"]

    # Combined discount (bonus + coupon + promo) must not exceed the goods
    # subtotal, otherwise the buyer would pay only delivery while sellers are
    # still owed their full net. Cap the stack and trim the bonus portion first.
    discount = (bonus_to_use + coupon_discount + promo_discount).quantize(Decimal("0.01"))
    if discount > subtotal:
        overflow = discount - subtotal
        bonus_to_use = max(Decimal("0.00"), bonus_to_use - overflow)
        discount = (bonus_to_use + coupon_discount + promo_discount).quantize(Decimal("0.01"))
        if discount > subtotal:
            discount = subtotal
    # Gift wrapping is a paid add-on (admin-tunable gift_wrap_price), charged on
    # top of the goods+delivery and folded into the order total.
    gift_wrap_cost = Decimal("0.00")
    if payload.gift_wrap:
        from app.services.settings_service import get_setting
        try:
            gift_wrap_cost = Decimal((await get_setting(db, "gift_wrap_price")) or "0").quantize(Decimal("0.01"))
        except Exception:
            gift_wrap_cost = Decimal("0.00")

    total_price = max(
        (subtotal + delivery_cost + gift_wrap_cost - discount).quantize(Decimal("0.01")),
        Decimal("1.00"),
    )

    # Promo balance (gift certificates) is spent like money on the remaining
    # payable, after all percentage/coupon/bonus discounts.
    promo_used = Decimal("0.00")
    if (current_user.promo_balance or Decimal("0.00")) > 0 and total_price > Decimal("1.00"):
        spendable = (total_price - Decimal("1.00")).quantize(Decimal("0.01"))
        promo_used = await gift_service.spend_promo(
            db, current_user, spendable, "Оплата заказа промо-балансом"
        )
        total_price = (total_price - promo_used).quantize(Decimal("0.01"))

    # 7c. Referral earnings can pay up to 100% of the remaining total. To respect
    # the gateway's 1₽ minimum, the leftover is forced to be either 0 (fully paid)
    # or ≥ 1.00 (paid via gateway).
    referral_used = Decimal("0.00")
    want_ref = min(payload.referral_to_use or Decimal("0.00"), current_user.referral_balance or Decimal("0.00"))
    if want_ref > 0 and total_price > 0:
        use = min(want_ref, total_price)
        remainder = total_price - use
        if Decimal("0.00") < remainder < Decimal("1.00"):
            if want_ref >= total_price:
                use = total_price                       # fully cover
            else:
                use = max(Decimal("0.00"), total_price - Decimal("1.00"))  # leave 1₽ for gateway
        referral_used = use.quantize(Decimal("0.01"))
        current_user.referral_balance = (current_user.referral_balance - referral_used).quantize(Decimal("0.01"))
        total_price = (total_price - referral_used).quantize(Decimal("0.01"))

    free_order = total_price <= Decimal("0.00")

    # BNPL ("Сплит"): the provider settles the marketplace upfront, so the order
    # is paid immediately and the buyer repays in parts per the schedule.
    bnpl = False
    bnpl_cfg = None
    if payload.payment_method == "split" and not free_order:
        from app.services import bnpl_service
        bnpl_cfg = await bnpl_service.config(db)
        if not bnpl_service.is_eligible(total_price, bnpl_cfg):
            raise HTTPException(status_code=400, detail="Оплата частями недоступна для этого заказа")
        bnpl = True

    # 8. Create order
    order = Order(
        buyer_id=current_user.id,
        total_price=total_price,
        subtotal=subtotal,
        delivery_cost=delivery_cost,
        platform_fee=total_platform_fee,
        seller_net=total_seller_net,
        commission_percent_used=blended_commission_percent,
        bonus_used=bonus_to_use,
        promo_used=promo_used,
        referral_used=referral_used,
        coupon_discount=coupon_discount,
        status=OrderStatus.pending_payment,
        delivery_address=payload.delivery_address,
        coupon_id=coupon_obj.id if coupon_obj else None,
        is_gift=payload.is_gift or payload.gift_wrap or bool(payload.gift_message),
        gift_wrap=payload.gift_wrap,
        gift_message=(payload.gift_message or None),
    )
    db.add(order)
    await db.flush()

    # 9. Create order items (with their own per-shop financials) and reserve stock.
    # Reserve in a deterministic (product_id, variant_id) order so concurrent
    # checkouts acquire the row locks in the same sequence and never deadlock.
    from app.services.stock_service import reserve_stock
    for item_data in sorted(
        item_financials,
        key=lambda d: (d["product"].id, d.get("variant").id if d.get("variant") else 0),
    ):
        variant = item_data.get("variant")
        oi = OrderItem(
            order_id=order.id,
            product_id=item_data["product"].id,
            variant_id=variant.id if variant else None,
            variant_name=variant.name if variant else None,
            shop_id=item_data["product"].shop_id,
            quantity=item_data["quantity"],
            price_at_time=item_data["price_at_time"],
            commission_percent_used=item_data["commission_percent_used"],
            platform_fee=item_data["platform_fee"],
            seller_net=item_data["seller_net"],
            payout_status="pending",
        )
        db.add(oi)
        # Only physical goods reserve stock. Digital/course items are unlimited.
        if item_data["product"].product_type == ProductType.physical:
            # Atomically lock the row, re-validate availability and decrement —
            # this is the authoritative stock check (the loop at step 2 is only a
            # fast pre-flight and is not race-safe on its own).
            try:
                await reserve_stock(
                    db, item_data["product"].id, item_data["quantity"],
                    variant_id=variant.id if variant else None,
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc))

    await db.flush()

    # 9b. Split the order into per-seller sub-orders so each seller manages
    # their own fulfillment status and tracking independently.
    from app.services.suborder_service import create_sub_orders_for_order
    await create_sub_orders_for_order(order, db)

    # 10. Create delivery info (only for orders that actually ship)
    if has_physical and rate is not None:
        delivery = DeliveryInfo(
            order_id=order.id,
            delivery_service=rate.service,
            cost=delivery_cost,
            estimated_days=rate.estimated_days,
            city_from="Москва",
            city_to=payload.city_to,
            address=payload.delivery_address,
        )
        db.add(delivery)

    # 11. Deduct bonus from buyer
    if bonus_to_use > 0:
        current_user.bonus_balance -= bonus_to_use
        bal_tx = BalanceTransaction(
            user_id=current_user.id,
            change=-bonus_to_use,
            type=BalanceTransactionType.debit,
            reference_type="order",
            reference_id=order.id,
            description=f"Оплата бонусами по заказу #{order.id}",
            balance_after=current_user.bonus_balance,
        )
        db.add(bal_tx)

    # 11b. Ledger entry for referral balance spent on this order
    if referral_used > 0:
        db.add(BalanceTransaction(
            user_id=current_user.id,
            change=-referral_used,
            type=BalanceTransactionType.debit,
            reference_type="order",
            reference_id=order.id,
            description=f"Оплата реферальным балансом по заказу #{order.id}",
            balance_after=current_user.referral_balance,
        ))

    # 12. Clear cart
    for item in cart_items:
        await db.delete(item)

    await db.flush()

    # 13/14 (paid upfront): either the referral balance fully covered the total
    # (free order) OR a BNPL provider settled the marketplace upfront. No gateway
    # charge — mark it paid, record the installment plan (BNPL), grant digital
    # access, and complete a digital-only order (mirrors the YooKassa webhook).
    if free_order or bnpl:
        from datetime import datetime, timezone
        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.split if bnpl else PaymentGateway.yookassa,
            amount=order.total_price if bnpl else Decimal("0.00"),
            status=PaymentStatus.succeeded, paid_at=datetime.now(timezone.utc),
        )
        db.add(payment)
        if bnpl:
            from app.services import bnpl_service
            await bnpl_service.create_for_order(db, order, bnpl_cfg)
        order.status = OrderStatus.paid
        await db.flush()
        order_full = (await db.execute(
            select(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
            .where(Order.id == order.id)
        )).scalar_one()
        from app.services import entitlement_service
        await entitlement_service.grant_for_order(db, order_full)
        if entitlement_service.order_is_digital_only(order_full):
            order.status = OrderStatus.completed
            await payout_sellers_for_order(order_full, db)
            await process_buyer_referral_reward(order_full, db)
            await process_seller_referral_reward(order_full, db)
            from app.services.loyalty_service import award_cashback_for_order
            await award_cashback_for_order(order_full, db)
        await db.commit()
        await db.refresh(order)
        result_obj = await db.execute(
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.images),
                selectinload(Order.payment),
                selectinload(Order.delivery_info),
            )
            .where(Order.id == order.id)
        )
        return result_obj.scalar_one()

    # 13. Build the 54-ФЗ fiscal receipt (приход) so YooKassa registers it in
    # the ОФД automatically once the payment succeeds.
    fiscal_receipt: Optional[dict] = None
    fiscal_contact = ""
    fiscal_tax_system = None
    if settings.FISCAL_ENABLED:
        try:
            item_ctx = [
                {
                    "title": d["product"].title,
                    "quantity": d["quantity"],
                    "unit_price": d["price_at_time"],
                    "shop_id": d["product"].shop_id,
                }
                for d in item_financials
            ]
            line_items, fiscal_tax_system = await fiscal_service.build_income_line_items(db, item_ctx)
            fiscal_contact = fiscal_service.customer_contact(current_user)
            fiscal_receipt = fiscal_service.build_receipt(
                fiscal_contact, line_items,
                delivery_cost=delivery_cost, tax_system_code=fiscal_tax_system,
            )
        except Exception:
            fiscal_receipt = None

    # 14. Create YooKassa payment (with the embedded receipt when available)
    try:
        payment_gw = get_payment_gateway()
        result = await payment_gw.create_payment(
            order_id=order.id,
            amount=total_price,
            description=f"Заказ #{order.id} на маркетплейсе",
            return_url=None,
            receipt=fiscal_receipt,
        )
        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.yookassa,
            gateway_payment_id=result.gateway_payment_id,
            amount=total_price,
            status=PaymentStatus.pending,
            confirmation_url=result.confirmation_url,
        )
    except Exception:
        # If payment gateway fails, create pending payment without URL
        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.yookassa,
            amount=total_price,
            status=PaymentStatus.pending,
        )
    db.add(payment)
    await db.flush()

    # Snapshot a pending fiscal receipt so the registration outcome (reported via
    # the payment webhook) can be tracked and shown to the buyer.
    if fiscal_receipt is not None:
        try:
            await fiscal_service.create_pending_receipt(
                db, order, FiscalReceiptType.income, fiscal_contact, total_price,
                fiscal_receipt, fiscal_tax_system, payment_id=payment.id,
            )
        except Exception:
            pass

    # Notify each distinct shop owner that they have a new order
    from app.services.notification_service import notify as _notify_new_order
    from app.models.models import NotificationType as _NT_order
    notified_shops = set()
    for item_data in item_financials:
        sid = item_data["product"].shop_id
        if sid in notified_shops:
            continue
        notified_shops.add(sid)
        shop_obj = shops.get(sid)
        if shop_obj:
            await _notify_new_order(
                db, shop_obj.owner_id, _NT_order.new_order,
                title="Новый заказ!",
                body=f"Заказ #{order.id}",
                link="/seller/orders",
            )

    await db.commit()
    await db.refresh(order)

    # Reload with relationships
    result_obj = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.images),
            selectinload(Order.payment),
            selectinload(Order.delivery_info),
        )
        .where(Order.id == order.id)
    )
    return result_obj.scalar_one()


@router.get("", response_model=dict)
async def list_my_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = (
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.images),
            selectinload(Order.payment),
            selectinload(Order.delivery_info),
        )
        .where(Order.buyer_id == current_user.id)
        .order_by(Order.created_at.desc())
    )
    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    orders = result.scalars().all()
    return {
        "items": [OrderOut.model_validate(o) for o in orders],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.get("/seller/my", response_model=dict)
async def list_seller_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Orders containing at least one item from the current seller's shop.
    Distinct from list_my_orders, which returns orders the user placed AS a
    buyer — a seller's own sales are a completely different query.
    """
    shop_result = await db.execute(select(Shop).where(Shop.owner_id == current_user.id))
    shop = shop_result.scalar_one_or_none()
    if not shop:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 1}

    base_query = (
        select(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(OrderItem.shop_id == shop.id)
        .distinct()
    )
    total_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar_one()

    query = (
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.images),
            selectinload(Order.payment),
            selectinload(Order.delivery_info),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(OrderItem.shop_id == shop.id)
        .distinct()
        .order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    orders = result.scalars().all()
    return {
        "items": [OrderOut.model_validate(o) for o in orders],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.images),
            selectinload(Order.payment),
            selectinload(Order.delivery_info),
        )
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Access check: buyer or seller of the products
    if order.buyer_id != current_user.id:
        # Check if current user is the seller
        shop_result = await db.execute(select(Shop).where(Shop.owner_id == current_user.id))
        shop = shop_result.scalar_one_or_none()
        if not shop:
            raise HTTPException(status_code=403, detail="Access denied")
        product_ids = [item.product_id for item in order.items]
        seller_products = await db.execute(
            select(Product.id).where(Product.id.in_(product_ids), Product.shop_id == shop.id)
        )
        if not seller_products.scalars().all():
            raise HTTPException(status_code=403, detail="Access denied")

    return order


@router.patch("/{order_id}/status", response_model=OrderOut)
async def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seller can update status to shipped. Buyer can cancel."""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.images),
            selectinload(Order.payment),
            selectinload(Order.delivery_info),
        )
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Authorization
    is_buyer = order.buyer_id == current_user.id
    shop_result = await db.execute(select(Shop).where(Shop.owner_id == current_user.id))
    shop = shop_result.scalar_one_or_none()
    # Critical: is_seller must verify the seller actually has items in THIS
    # order, not merely that they own some shop on the platform — otherwise
    # any seller could change the status of any other seller's order.
    is_seller = bool(shop) and any(item.shop_id == shop.id for item in order.items)

    allowed_transitions = {
        OrderStatus.paid: [OrderStatus.processing, OrderStatus.cancelled],
        OrderStatus.processing: [OrderStatus.shipped],
        OrderStatus.shipped: [OrderStatus.delivered],
        OrderStatus.delivered: [OrderStatus.completed],
        OrderStatus.pending_payment: [OrderStatus.cancelled],
    }

    if payload.status not in allowed_transitions.get(order.status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {order.status} to {payload.status}",
        )

    if payload.status in (OrderStatus.shipped,) and not is_seller:
        raise HTTPException(status_code=403, detail="Only seller can mark order as shipped")
    if payload.status == OrderStatus.cancelled and not (is_buyer or is_seller):
        raise HTTPException(status_code=403, detail="Access denied")

    # Capture the prior status before overwriting, since several checks below
    # need to know what the order transitioned FROM (e.g. refund-on-cancel
    # only applies if it was actually paid before being cancelled).
    previous_status = order.status
    order.status = payload.status

    if payload.tracking_number and order.delivery_info:
        from datetime import datetime, timezone
        order.delivery_info.tracking_number = payload.tracking_number
        order.delivery_info.shipped_at = datetime.now(timezone.utc)

    # On completion: credit every seller represented in this order their own
    # share (an order can span multiple shops, each with its own commission).
    if payload.status == OrderStatus.completed:
        await payout_sellers_for_order(order, db)
        await process_buyer_referral_reward(order, db)
        await process_seller_referral_reward(order, db)
        from app.services.loyalty_service import award_cashback_for_order
        await award_cashback_for_order(order, db)

    # Notify the buyer about any status change
    from app.services.notification_service import notify as _notify
    from app.models.models import NotificationType as _NT
    await _notify(
        db, order.buyer_id, _NT.order_status,
        title=f"Заказ #{order.id}: статус изменён",
        body=f"Новый статус: {payload.status.value}",
        link=f"/orders/{order.id}",
    )

    if payload.status == OrderStatus.cancelled:
        # Money is only returned via the gateway when the order was actually
        # paid before this cancellation (checked against previous_status, not
        # the already-overwritten order.status).
        if previous_status == OrderStatus.paid and order.payment and order.payment.gateway_payment_id:
            # 54-ФЗ: build a full refund receipt (возврат прихода) mirroring the
            # order so YooKassa registers the refund fiscal document.
            refund_receipt = None
            refund_tax_system = None
            refund_contact = ""
            if settings.FISCAL_ENABLED:
                try:
                    buyer = (await db.execute(select(User).where(User.id == order.buyer_id))).scalar_one_or_none()
                    item_ctx = [
                        {"title": it.product.title, "quantity": it.quantity,
                         "unit_price": it.price_at_time, "shop_id": it.shop_id}
                        for it in order.items
                    ]
                    line_items, refund_tax_system = await fiscal_service.build_income_line_items(db, item_ctx)
                    refund_contact = fiscal_service.customer_contact(buyer) if buyer else ""
                    refund_receipt = fiscal_service.build_receipt(
                        refund_contact, line_items,
                        delivery_cost=order.delivery_cost, tax_system_code=refund_tax_system,
                    )
                except Exception:
                    refund_receipt = None
            try:
                gw = get_payment_gateway()
                await gw.refund_payment(order.payment.gateway_payment_id, order.total_price, receipt=refund_receipt)
                # Mark refunded here so the gateway's own "refunded" webhook
                # (which this call triggers) sees the order already cancelled
                # and skips the reversal instead of double-restoring.
                order.payment.status = PaymentStatus.refunded
            except Exception:
                pass  # Log in production
            if refund_receipt is not None:
                try:
                    await fiscal_service.create_pending_receipt(
                        db, order, FiscalReceiptType.income_refund, refund_contact,
                        order.total_price, refund_receipt, refund_tax_system,
                        payment_id=order.payment.id,
                    )
                except Exception:
                    pass
        # Restore stock + buyer bonus/promo + coupon usage. This runs for ANY
        # cancellation (paid or still-pending-payment), since stock is reserved
        # at order creation regardless of payment state.
        from app.services.order_reversal_service import restore_order
        await restore_order(db, order)

    await db.commit()
    await db.refresh(order)
    return order


@router.get("/{order_id}/installment-plan")
async def get_installment_plan(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The BNPL schedule for an order (buyer-owned). Returns null if not on a plan."""
    import json
    from app.models.models import InstallmentPlan
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order or order.buyer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    plan = (await db.execute(
        select(InstallmentPlan).where(InstallmentPlan.order_id == order_id)
    )).scalar_one_or_none()
    if not plan:
        return None
    return {
        "provider": plan.provider, "total": str(plan.total),
        "parts": plan.parts, "part_amount": str(plan.part_amount),
        "status": plan.status,
        "schedule": json.loads(plan.schedule) if plan.schedule else [],
    }


@router.get("/{order_id}/receipts", response_model=list[FiscalReceiptOut])
async def get_order_receipts(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fiscal receipts (54-ФЗ) for an order. Accessible to the buyer, a seller
    with items in the order, or staff."""
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.buyer_id != current_user.id and not current_user.is_staff:
        shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
        is_seller = bool(shop) and any(item.shop_id == shop.id for item in order.items)
        if not is_seller:
            raise HTTPException(status_code=403, detail="Access denied")

    return await fiscal_service.get_order_receipts(db, order_id)


@router.post("/webhook/yookassa")
async def yookassa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle YooKassa payment notifications."""
    body = await request.body()

    # Behind the nginx reverse proxy (see frontend/nginx.conf), the real
    # client IP arrives in X-Forwarded-For rather than request.client.host,
    # which would otherwise just be the proxy's own address.
    forwarded_for = request.headers.get("x-forwarded-for")
    source_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (
        request.client.host if request.client else None
    )

    gw = get_payment_gateway()
    if not gw.verify_webhook(body, dict(request.headers), source_ip=source_ip):
        raise HTTPException(status_code=400, detail="Invalid webhook")

    try:
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if data.get("type") != "notification":
        return {"status": "ignored"}

    obj = data.get("object", {})
    gateway_payment_id = obj.get("id")
    yoo_status = obj.get("status")

    if not gateway_payment_id:
        return {"status": "ignored"}

    result = await db.execute(
        select(Payment).where(Payment.gateway_payment_id == gateway_payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        return {"status": "not_found"}

    order_result = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .where(Order.id == payment.order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        return {"status": "order_not_found"}

    if yoo_status == "succeeded":
        # Idempotency: YooKassa re-delivers notifications until it gets a 200.
        # Only run the transition the first time (while still pending), so a
        # retried webhook never re-applies anything.
        if payment.status != PaymentStatus.pending:
            return {"status": "ok"}
        from datetime import datetime, timezone
        payment.status = PaymentStatus.succeeded
        payment.paid_at = datetime.now(timezone.utc)
        order.status = OrderStatus.paid
        # 54-ФЗ: YooKassa reports the ОФД registration outcome in
        # receipt_registration (succeeded/pending/canceled). Reflect it on the
        # order's income fiscal receipt(s).
        registration = obj.get("receipt_registration")
        income_receipts = (await db.execute(
            select(FiscalReceipt).where(
                FiscalReceipt.payment_id == payment.id,
                FiscalReceipt.type == FiscalReceiptType.income,
            )
        )).scalars().all()
        for fr in income_receipts:
            fiscal_service.apply_registration(fr, registration, raw=obj)

        # Digital fulfillment: grant access immediately on payment. If the order
        # is digital-only (nothing to ship), complete it now so the seller is paid
        # and the buyer can download right away.
        from app.services import entitlement_service
        await entitlement_service.grant_for_order(db, order)
        if entitlement_service.order_is_digital_only(order):
            order.status = OrderStatus.completed
            await payout_sellers_for_order(order, db)
            await process_buyer_referral_reward(order, db)
            await process_seller_referral_reward(order, db)
            from app.services.loyalty_service import award_cashback_for_order
            await award_cashback_for_order(order, db)
            from app.services.notification_service import notify as _notify_ready
            from app.models.models import NotificationType as _NT_ready
            await _notify_ready(
                db, order.buyer_id, _NT_ready.order_status,
                title="Покупка готова",
                body=f"Заказ #{order.id}: цифровые товары доступны в разделе «Мои покупки»",
                link="/my/downloads",
            )
    elif yoo_status in ("cancelled", "refunded"):
        # Idempotency: skip if this order was already cancelled — either by a
        # prior delivery of this same webhook, or by a manual cancel (which
        # also issues the gateway refund that triggers THIS notification).
        # Without this guard the stock/balances would be restored twice.
        if order.status == OrderStatus.cancelled:
            return {"status": "ok"}
        payment.status = (
            PaymentStatus.refunded if yoo_status == "refunded" else PaymentStatus.cancelled
        )
        order.status = OrderStatus.cancelled
        # Restore stock + buyer bonus/promo + coupon usage in one place.
        from app.services.order_reversal_service import restore_order
        await restore_order(db, order)

    await db.commit()
    return {"status": "ok"}

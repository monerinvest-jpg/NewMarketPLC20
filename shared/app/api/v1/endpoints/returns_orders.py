"""
Items 1, 3, 7 endpoints: returns (RMA), sub-order fulfillment, and
product back-in-stock / price-drop subscriptions.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_user, get_current_seller
from app.core.database import get_db
from app.models.models import (
    NotificationType, Order, OrderItem, Product, ProductSubscription,
    ReturnRequest, ReturnRequestStatus, Shop, SubOrder, SubOrderStatus, User,
)
from app.schemas.schemas import (
    ProductSubscriptionCreate, ProductSubscriptionOut, ReturnProcessRequest,
    ReturnRequestCreate, ReturnRequestOut, SubOrderOut, SubOrderStatusUpdate,
)
from app.services.notification_service import notify
from app.services.return_service import refund_return
from app.services.suborder_service import recompute_order_status

router = APIRouter(tags=["returns-suborders"])


# ─── Returns (RMA) ───────────────────────────────────────────────────────────────

@router.post("/returns", response_model=ReturnRequestOut, status_code=201)
async def create_return(
    payload: ReturnRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (await db.execute(
        select(OrderItem).options(selectinload(OrderItem.order)).where(OrderItem.id == payload.order_item_id)
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Позиция заказа не найдена")
    if item.order.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваш заказ")
    if payload.quantity > item.quantity:
        raise HTTPException(status_code=400, detail="Количество превышает заказанное")

    # Prevent duplicate open returns for the same item
    existing = (await db.execute(
        select(ReturnRequest).where(
            ReturnRequest.order_item_id == item.id,
            ReturnRequest.status.in_([
                ReturnRequestStatus.requested, ReturnRequestStatus.approved,
                ReturnRequestStatus.in_transit,
            ]),
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="По этой позиции уже есть активная заявка на возврат")

    ret = ReturnRequest(
        order_item_id=item.id,
        buyer_id=current_user.id,
        shop_id=item.shop_id,
        quantity=payload.quantity,
        reason=payload.reason,
        status=ReturnRequestStatus.requested,
    )
    db.add(ret)
    await db.flush()

    shop = (await db.execute(select(Shop).where(Shop.id == item.shop_id))).scalar_one_or_none()
    if shop:
        await notify(
            db, shop.owner_id, NotificationType.order_status,
            title="Новая заявка на возврат",
            body=payload.reason[:120], link="/seller/returns",
        )
    await db.commit()
    await db.refresh(ret)
    return ret


@router.get("/returns/my", response_model=list[ReturnRequestOut])
async def my_returns(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ReturnRequest).where(ReturnRequest.buyer_id == current_user.id)
        .order_by(ReturnRequest.created_at.desc())
    )
    return result.scalars().all()


@router.get("/returns/seller", response_model=list[ReturnRequestOut])
async def seller_returns(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="У вас нет магазина")
    result = await db.execute(
        select(ReturnRequest).where(ReturnRequest.shop_id == shop.id)
        .order_by(ReturnRequest.created_at.desc())
    )
    return result.scalars().all()


@router.post("/returns/{return_id}/process", response_model=ReturnRequestOut)
async def process_return(
    return_id: int,
    payload: ReturnProcessRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Seller (or admin) advances a return: approve, reject, mark in_transit, or refund."""
    ret = (await db.execute(select(ReturnRequest).where(ReturnRequest.id == return_id))).scalar_one_or_none()
    if not ret:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    if not shop or ret.shop_id != shop.id:
        if not (current_user.is_superuser or current_user.is_staff):
            raise HTTPException(status_code=403, detail="Нет доступа к этой заявке")

    new_status = ReturnRequestStatus(payload.status)
    ret.resolution_comment = payload.resolution_comment
    ret.processed_by_id = current_user.id
    ret.processed_at = datetime.now(timezone.utc)
    if payload.refund_amount is not None:
        ret.refund_amount = payload.refund_amount

    if new_status == ReturnRequestStatus.refunded:
        await refund_return(ret, db)
    else:
        ret.status = new_status
        await notify(
            db, ret.buyer_id, NotificationType.order_status,
            title=f"Заявка на возврат: {payload.status}",
            body=payload.resolution_comment or "", link="/orders",
        )

    await db.commit()
    await db.refresh(ret)
    return ret


# ─── Sub-orders (per-seller fulfillment) ────────────────────────────────────────

@router.get("/seller/sub-orders")
async def list_seller_sub_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """
    All sub-orders belonging to the current seller's shop, with lightweight
    order context (date, buyer-facing order id, the seller's own item lines and
    net total). Lets a seller manage fulfillment of just their slice.
    """
    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    subs = (await db.execute(
        select(SubOrder).where(SubOrder.shop_id == shop.id).order_by(SubOrder.created_at.desc())
    )).scalars().all()

    out = []
    for so in subs:
        order = (await db.execute(select(Order).where(Order.id == so.order_id))).scalar_one_or_none()
        items = (await db.execute(
            select(OrderItem).options(selectinload(OrderItem.product))
            .where(OrderItem.sub_order_id == so.id)
        )).scalars().all()
        net = sum((i.seller_net for i in items), Decimal("0"))
        out.append({
            "id": so.id,
            "order_id": so.order_id,
            "status": so.status.value,
            "tracking_number": so.tracking_number,
            "delivery_service": so.delivery_service,
            "created_at": order.created_at.isoformat() if order else None,
            "net_total": float(net),
            "items": [
                {"title": i.product.title if i.product else "—",
                 "variant_name": i.variant_name,
                 "quantity": i.quantity,
                 "price_at_time": float(i.price_at_time)}
                for i in items
            ],
        })
    return out


@router.get("/orders/{order_id}/sub-orders")
async def get_sub_orders(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Per-seller sub-orders for an order, enriched with shop name, the items in
    each shop's shipment, and a tracking URL when a carrier + number are known.
    Visible to the order's buyer (and to a seller for their own shop).
    """
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    is_buyer = order and order.buyer_id == current_user.id
    seller_shop = None
    if not is_buyer:
        seller_shop = (await db.execute(
            select(Shop).where(Shop.owner_id == current_user.id)
        )).scalar_one_or_none()
        if not order or not seller_shop:
            raise HTTPException(status_code=404, detail="Заказ не найден")

    subs = (await db.execute(
        select(SubOrder).where(SubOrder.order_id == order_id)
    )).scalars().all()

    out = []
    for so in subs:
        # A seller may only see their own sub-order
        if seller_shop and so.shop_id != seller_shop.id:
            continue
        shop = (await db.execute(select(Shop).where(Shop.id == so.shop_id))).scalar_one_or_none()
        items = (await db.execute(
            select(OrderItem).options(selectinload(OrderItem.product))
            .where(OrderItem.sub_order_id == so.id)
        )).scalars().all()
        out.append({
            "id": so.id,
            "shop_id": so.shop_id,
            "shop_name": shop.name if shop else None,
            "status": so.status.value,
            "tracking_number": so.tracking_number,
            "delivery_service": so.delivery_service,
            "tracking_url": _tracking_url(so.delivery_service, so.tracking_number),
            "items": [
                {"title": i.product.title if i.product else "—",
                 "variant_name": i.variant_name,
                 "quantity": i.quantity}
                for i in items
            ],
        })
    return out


def _tracking_url(service: str | None, number: str | None) -> str | None:
    """Build a public tracking URL for known Russian carriers."""
    if not number:
        return None
    s = (service or "").lower()
    if "cdek" in s or "сдэк" in s:
        return f"https://www.cdek.ru/ru/tracking?order_id={number}"
    if "post" in s or "почта" in s or "russianpost" in s:
        return f"https://www.pochta.ru/tracking#{number}"
    if "boxberry" in s:
        return f"https://boxberry.ru/tracking-page?id={number}"
    return None


@router.patch("/sub-orders/{sub_order_id}/status", response_model=SubOrderOut)
async def update_sub_order_status(
    sub_order_id: int,
    payload: SubOrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Seller updates the fulfillment status of their slice of an order."""
    so = (await db.execute(select(SubOrder).where(SubOrder.id == sub_order_id))).scalar_one_or_none()
    if not so:
        raise HTTPException(status_code=404, detail="Под-заказ не найден")
    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    if not shop or so.shop_id != shop.id:
        raise HTTPException(status_code=403, detail="Это не ваш под-заказ")

    so.status = SubOrderStatus(payload.status)
    if payload.tracking_number is not None:
        so.tracking_number = payload.tracking_number

    # Recompute the parent order's overall status from all sub-orders
    order = (await db.execute(select(Order).where(Order.id == so.order_id))).scalar_one_or_none()
    if order:
        await recompute_order_status(order, db)
        await notify(
            db, order.buyer_id, NotificationType.order_status,
            title=f"Заказ #{order.id}: обновление доставки",
            body=f"Магазин обновил статус: {payload.status}", link=f"/orders/{order.id}",
            send_sms=True,
        )

    await db.commit()
    await db.refresh(so)
    return so


@router.post("/sub-orders/{sub_order_id}/shipment")
async def create_sub_order_shipment(
    sub_order_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """
    Register a shipment with the carrier for this sub-order. On success stores
    the carrier tracking number + uuid and marks the sub-order shipped. Falls
    back to a mock shipment (deterministic tracking number) when the carrier has
    no API key, so the flow always completes.
    """
    so = (await db.execute(select(SubOrder).where(SubOrder.id == sub_order_id))).scalar_one_or_none()
    if not so:
        raise HTTPException(status_code=404, detail="Под-заказ не найден")
    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    if not shop or so.shop_id != shop.id:
        raise HTTPException(status_code=403, detail="Это не ваш под-заказ")

    order = (await db.execute(select(Order).where(Order.id == so.order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    service = payload.get("delivery_service") or so.delivery_service or "cdek"
    items = (await db.execute(
        select(OrderItem).options(selectinload(OrderItem.product))
        .where(OrderItem.sub_order_id == so.id)
    )).scalars().all()
    total_weight = sum((i.product.weight_g if i.product else 500) * i.quantity for i in items) or 500

    from app.services.delivery_service import get_delivery_gateway
    gateway = get_delivery_gateway(service)

    shipment = {
        "order_number": f"{order.id}-{so.id}",
        "tariff_code": payload.get("tariff_code", 136),
        "from_city": shop.name and payload.get("from_city", "Москва") or "Москва",
        "to_city": payload.get("to_city", ""),
        "to_address": order.delivery_address or "",
        "recipient_name": payload.get("recipient_name", ""),
        "recipient_phone": payload.get("recipient_phone", ""),
        "weight_g": total_weight,
        "items": [
            {"name": (i.product.title if i.product else "Товар")[:60],
             "ware_key": str(i.product_id), "cost": float(i.price),
             "weight": (i.product.weight_g if i.product else 500), "amount": i.quantity}
            for i in items
        ],
    }
    result = await gateway.create_shipment(shipment)
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.error or "Не удалось оформить отгрузку")

    so.carrier_uuid = result.carrier_uuid
    so.delivery_service = service
    if result.tracking_number:
        so.tracking_number = result.tracking_number
    so.status = SubOrderStatus.shipped
    await recompute_order_status(order, db)
    await notify(
        db, order.buyer_id, NotificationType.order_status,
        title=f"Заказ #{order.id}: отправлен",
        body=f"Трек-номер: {so.tracking_number or '—'}", link=f"/orders/{order.id}",
        send_sms=True,
    )
    await db.commit()
    await db.refresh(so)
    return {
        "ok": True,
        "tracking_number": so.tracking_number,
        "carrier_uuid": so.carrier_uuid,
        "delivery_service": service,
    }


@router.get("/sub-orders/{sub_order_id}/label")
async def download_sub_order_label(
    sub_order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """
    Download a printable shipping label. Prefers the carrier's own label (via API
    using carrier_uuid); falls back to a self-generated A6 PDF with a Code128
    barcode of the tracking number.
    """
    from fastapi.responses import Response

    so = (await db.execute(select(SubOrder).where(SubOrder.id == sub_order_id))).scalar_one_or_none()
    if not so:
        raise HTTPException(status_code=404, detail="Под-заказ не найден")
    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    if not shop or so.shop_id != shop.id:
        raise HTTPException(status_code=403, detail="Это не ваш под-заказ")
    if not so.tracking_number:
        raise HTTPException(status_code=400, detail="Сначала оформите отгрузку")

    order = (await db.execute(select(Order).where(Order.id == so.order_id))).scalar_one_or_none()
    items = (await db.execute(
        select(OrderItem).options(selectinload(OrderItem.product))
        .where(OrderItem.sub_order_id == so.id)
    )).scalars().all()

    # 1) Try the carrier's own label
    pdf_bytes = None
    if so.carrier_uuid and not so.carrier_uuid.startswith("mock-"):
        from app.services.delivery_service import get_delivery_gateway
        gateway = get_delivery_gateway(so.delivery_service or "cdek")
        try:
            pdf_bytes = await gateway.get_label(so.carrier_uuid)
        except Exception:
            pdf_bytes = None

    # 2) Fall back to our own generated label
    if not pdf_bytes:
        from app.services.label_service import generate_label_pdf
        total_weight = sum((i.product.weight_g if i.product else 500) * i.quantity for i in items) or 500
        items_summary = ", ".join(
            f"{(i.product.title if i.product else 'Товар')[:20]}×{i.quantity}" for i in items
        )[:120]
        pdf_bytes = generate_label_pdf(
            tracking_number=so.tracking_number,
            carrier=(so.delivery_service or "cdek").upper(),
            order_number=f"{order.id}-{so.id}" if order else str(so.id),
            sender_name=shop.name,
            recipient_name=order.delivery_address.split(",")[0] if order and order.delivery_address else "Получатель",
            recipient_phone="",
            recipient_address=order.delivery_address if order else "",
            weight_g=total_weight,
            items_summary=items_summary,
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="label-{so.id}.pdf"'},
    )

@router.post("/product-subscriptions", response_model=ProductSubscriptionOut, status_code=201)
async def subscribe_to_product(
    payload: ProductSubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.kind not in ("back_in_stock", "price_drop"):
        raise HTTPException(status_code=400, detail="Неверный тип подписки")
    product = (await db.execute(select(Product).where(Product.id == payload.product_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    existing = (await db.execute(
        select(ProductSubscription).where(
            ProductSubscription.user_id == current_user.id,
            ProductSubscription.product_id == payload.product_id,
            ProductSubscription.kind == payload.kind,
        )
    )).scalar_one_or_none()
    if existing:
        existing.target_price = payload.target_price
        existing.is_notified = False
        await db.commit()
        await db.refresh(existing)
        return existing

    sub = ProductSubscription(
        user_id=current_user.id, product_id=payload.product_id,
        kind=payload.kind, target_price=payload.target_price,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


@router.get("/product-subscriptions/my", response_model=list[ProductSubscriptionOut])
async def my_product_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ProductSubscription).where(ProductSubscription.user_id == current_user.id)
    )
    return result.scalars().all()


@router.delete("/product-subscriptions/{sub_id}", status_code=204)
async def unsubscribe_from_product(
    sub_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = (await db.execute(
        select(ProductSubscription).where(
            ProductSubscription.id == sub_id,
            ProductSubscription.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Подписка не найдена")
    await db.delete(sub)
    await db.commit()

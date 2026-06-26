"""
Dispute arbitration endpoints.

- Buyer: open a dispute on an order, message, escalate to mediation, cancel.
- Seller: see disputes against the shop, message, concede a refund.
- Mediator (support/moderator/superadmin): queue, assign, resolve with outcome.
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_seller, get_current_support_staff, get_current_user
from app.core.database import get_db
from app.models.models import (
    Dispute, DisputeResolution, DisputeStatus, Order, OrderItem, Shop, User,
)
from app.schemas.schemas import (
    DisputeCreate, DisputeDetailOut, DisputeMessageCreate, DisputeMessageOut,
    DisputeOut, DisputeResolve,
)
from app.services import dispute_service

router = APIRouter(prefix="/disputes", tags=["disputes"])
seller_router = APIRouter(prefix="/seller/disputes", tags=["disputes-seller"])


# ─────────────────────────── Buyer ───────────────────────────

@router.post("", response_model=DisputeDetailOut)
async def open_dispute(
    payload: DisputeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (await db.execute(select(Order).where(Order.id == payload.order_id))).scalar_one_or_none()
    if not order or order.buyer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Determine the shop the dispute is against.
    if payload.order_item_id is not None:
        item = (await db.execute(
            select(OrderItem).where(OrderItem.id == payload.order_item_id, OrderItem.order_id == order.id)
        )).scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Позиция заказа не найдена")
        shop_id = item.shop_id
    else:
        first_item = (await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id).limit(1)
        )).scalar_one_or_none()
        if not first_item:
            raise HTTPException(status_code=400, detail="В заказе нет позиций")
        shop_id = first_item.shop_id

    dispute = await dispute_service.open_dispute(
        db, current_user, order, shop_id, payload.subject, payload.reason, payload.order_item_id
    )
    await db.commit()
    return await dispute_service.load_detail(db, dispute.id)


@router.get("", response_model=list[DisputeOut])
async def my_disputes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(Dispute).where(Dispute.buyer_id == current_user.id)
        .order_by(Dispute.last_message_at.desc())
    )).scalars().all()
    return list(rows)


@router.get("/{dispute_id}", response_model=DisputeDetailOut)
async def get_dispute(
    dispute_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dispute = await dispute_service.load_detail(db, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    role = await dispute_service.role_in_dispute(db, dispute, current_user)
    if role is None:
        raise HTTPException(status_code=403, detail="Нет доступа")
    return dispute


@router.post("/{dispute_id}/messages", response_model=DisputeMessageOut)
async def post_message(
    dispute_id: int,
    payload: DisputeMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dispute = (await db.execute(select(Dispute).where(Dispute.id == dispute_id))).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    role = await dispute_service.role_in_dispute(db, dispute, current_user)
    if role is None:
        raise HTTPException(status_code=403, detail="Нет доступа")
    if dispute.status in (DisputeStatus.resolved, DisputeStatus.cancelled):
        raise HTTPException(status_code=400, detail="Спор закрыт")
    msg = await dispute_service.add_message(db, dispute, current_user, role, payload.text)
    await db.commit()
    await db.refresh(msg)
    return msg


@router.post("/{dispute_id}/escalate", response_model=DisputeOut)
async def escalate_dispute(
    dispute_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dispute = (await db.execute(select(Dispute).where(Dispute.id == dispute_id))).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    role = await dispute_service.role_in_dispute(db, dispute, current_user)
    if role not in ("buyer", "seller"):
        raise HTTPException(status_code=403, detail="Нет доступа")
    if dispute.status != DisputeStatus.open:
        raise HTTPException(status_code=400, detail="Спор нельзя эскалировать")
    await dispute_service.escalate(db, dispute)
    await db.commit()
    await db.refresh(dispute)
    return dispute


@router.post("/{dispute_id}/cancel", response_model=DisputeOut)
async def cancel_dispute(
    dispute_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dispute = (await db.execute(select(Dispute).where(Dispute.id == dispute_id))).scalar_one_or_none()
    if not dispute or dispute.buyer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Спор не найден")
    if dispute.status == DisputeStatus.resolved:
        raise HTTPException(status_code=400, detail="Спор уже завершён")
    dispute.status = DisputeStatus.cancelled
    await db.commit()
    await db.refresh(dispute)
    return dispute


# ─────────────────────────── Seller ───────────────────────────

@seller_router.get("", response_model=list[DisputeOut])
async def seller_disputes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    rows = (await db.execute(
        select(Dispute).where(Dispute.shop_id == shop.id).order_by(Dispute.last_message_at.desc())
    )).scalars().all()
    return list(rows)


@router.post("/{dispute_id}/concede", response_model=DisputeOut)
async def seller_concede(
    dispute_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seller agrees to a full refund, resolving the dispute in the buyer's favor."""
    dispute = (await db.execute(select(Dispute).where(Dispute.id == dispute_id))).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    role = await dispute_service.role_in_dispute(db, dispute, current_user)
    if role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец может согласиться на возврат")
    if dispute.status in (DisputeStatus.resolved, DisputeStatus.cancelled):
        raise HTTPException(status_code=400, detail="Спор закрыт")

    # Refund the disputed item's value (or the order subtotal if no item).
    amount = Decimal("0.00")
    if dispute.order_item_id:
        item = (await db.execute(select(OrderItem).where(OrderItem.id == dispute.order_item_id))).scalar_one_or_none()
        if item:
            amount = (item.price_at_time * item.quantity)
    else:
        order = (await db.execute(select(Order).where(Order.id == dispute.order_id))).scalar_one_or_none()
        amount = order.subtotal if order else Decimal("0.00")

    await dispute_service.resolve(
        db, dispute, DisputeResolution.buyer_favor, amount,
        "Продавец согласился на возврат.", current_user
    )
    await db.commit()
    await db.refresh(dispute)
    return dispute


# ─────────────────────────── Mediator (staff) ───────────────────────────

@router.get("/staff/queue", response_model=list[DisputeOut])
async def staff_queue(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_support_staff),
    status_filter: str | None = Query(None, alias="status"),
):
    query = select(Dispute)
    if status_filter:
        try:
            query = query.where(Dispute.status == DisputeStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail="Недопустимый статус")
    else:
        query = query.where(Dispute.status == DisputeStatus.in_mediation)
    rows = (await db.execute(query.order_by(Dispute.last_message_at.desc()).limit(100))).scalars().all()
    return list(rows)


@router.post("/{dispute_id}/assign-me", response_model=DisputeOut)
async def assign_me(
    dispute_id: int,
    db: AsyncSession = Depends(get_db),
    me: User = Depends(get_current_support_staff),
):
    dispute = (await db.execute(select(Dispute).where(Dispute.id == dispute_id))).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    dispute.mediator_id = me.id
    if dispute.status == DisputeStatus.open:
        dispute.status = DisputeStatus.in_mediation
    await db.commit()
    await db.refresh(dispute)
    return dispute


@router.post("/{dispute_id}/resolve", response_model=DisputeOut)
async def resolve_dispute(
    dispute_id: int,
    payload: DisputeResolve,
    db: AsyncSession = Depends(get_db),
    me: User = Depends(get_current_support_staff),
):
    dispute = (await db.execute(select(Dispute).where(Dispute.id == dispute_id))).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    if dispute.status in (DisputeStatus.resolved, DisputeStatus.cancelled):
        raise HTTPException(status_code=400, detail="Спор уже закрыт")
    if dispute.mediator_id is None:
        dispute.mediator_id = me.id
    await dispute_service.resolve(
        db, dispute, payload.resolution, payload.refund_amount, payload.note, me
    )
    await db.commit()
    await db.refresh(dispute)
    return dispute


@router.get("/staff/stats")
async def staff_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_support_staff),
):
    async def count(*conds):
        return (await db.execute(select(func.count()).select_from(Dispute).where(*conds))).scalar_one()
    return {
        "open": await count(Dispute.status == DisputeStatus.open),
        "in_mediation": await count(Dispute.status == DisputeStatus.in_mediation),
        "resolved": await count(Dispute.status == DisputeStatus.resolved),
    }

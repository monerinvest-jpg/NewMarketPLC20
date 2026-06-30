"""
Custom / made-to-order requests (Etsy-style commissions).

Lifecycle: new → quoted (seller offer) → accepted (buyer) → in_production → ready
→ completed, with declined/cancelled branches. Buyer and seller negotiate via a
message thread. In-app settlement is out of scope for v1 — the accepted offer
(price/lead time/deposit) captures the agreement; payment is arranged via a normal
order or off-platform. Designed to extend into the order/payment flow later.

Routers live under existing Kong prefixes (no new routes):
  * buyer_router  (/orders/custom-requests)  — included in the orders service
  * seller_router (/seller/custom-requests)  — included in the sellers service
"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_seller, get_current_user
from app.core.database import get_db
from app.models.models import (
    CustomMessage, CustomRequest, CustomRequestStatus, NotificationType, Shop, User,
)

buyer_router = APIRouter(prefix="/orders/custom-requests", tags=["custom-orders-buyer"])
seller_router = APIRouter(prefix="/seller/custom-requests", tags=["custom-orders-seller"])


def _req_dict(r: CustomRequest, messages: bool = False) -> dict:
    d = {
        "id": r.id, "buyer_id": r.buyer_id, "shop_id": r.shop_id, "product_id": r.product_id,
        "title": r.title, "description": r.description,
        "budget": str(r.budget) if r.budget is not None else None,
        "deadline": r.deadline.isoformat() if r.deadline else None,
        "attachments": json.loads(r.attachments) if r.attachments else [],
        "status": r.status.value if hasattr(r.status, "value") else r.status,
        "quoted_price": str(r.quoted_price) if r.quoted_price is not None else None,
        "quoted_days": r.quoted_days,
        "deposit_percent": str(r.deposit_percent) if r.deposit_percent is not None else None,
        "offer_note": r.offer_note,
        "created_at": r.created_at.isoformat(),
    }
    if messages:
        d["messages"] = [
            {"id": m.id, "sender_id": m.sender_id, "text": m.text,
             "attachments": json.loads(m.attachments) if m.attachments else [],
             "created_at": m.created_at.isoformat()}
            for m in r.messages
        ]
    return d


async def _notify(db, user_id, title, body, link):
    from app.services.notification_service import notify
    try:
        await notify(db, user_id, NotificationType.system, title=title, body=body, link=link)
    except Exception:  # noqa: BLE001
        pass


async def _seller_shop_id(db: AsyncSession, user: User) -> int:
    from app.services.shop_membership_service import resolve_shop_id
    shop_id = await resolve_shop_id(db, user)
    if not shop_id:
        raise HTTPException(status_code=403, detail="У вас нет магазина")
    return shop_id


# ─── Buyer ──────────────────────────────────────────────────────────────────────

@buyer_router.post("", status_code=201)
async def create_request(payload: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    shop_id = payload.get("shop_id")
    if not shop_id or not payload.get("title") or not payload.get("description"):
        raise HTTPException(status_code=400, detail="Укажите магазин, заголовок и описание")
    shop = (await db.execute(select(Shop).where(Shop.id == int(shop_id)))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    deadline = None
    if payload.get("deadline"):
        try:
            deadline = datetime.fromisoformat(payload["deadline"])
        except ValueError:
            deadline = None
    req = CustomRequest(
        buyer_id=current_user.id, shop_id=int(shop_id), product_id=payload.get("product_id"),
        title=payload["title"][:255], description=payload["description"],
        budget=payload.get("budget"), deadline=deadline,
        attachments=json.dumps(payload.get("attachments") or []),
        status=CustomRequestStatus.new,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    await _notify(db, shop.owner_id, "Новый запрос на изготовление", req.title, "/seller/custom-requests")
    await db.commit()
    return _req_dict(req)


@buyer_router.get("")
async def my_requests(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(CustomRequest).where(CustomRequest.buyer_id == current_user.id).order_by(CustomRequest.created_at.desc())
    )).scalars().all()
    return [_req_dict(r) for r in rows]


@buyer_router.get("/{request_id}")
async def get_request_buyer(request_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    r = (await db.execute(
        select(CustomRequest).options(selectinload(CustomRequest.messages)).where(CustomRequest.id == request_id)
    )).scalar_one_or_none()
    if not r or r.buyer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    return _req_dict(r, messages=True)


@buyer_router.post("/{request_id}/message")
async def buyer_message(request_id: int, payload: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    r = (await db.execute(select(CustomRequest).where(CustomRequest.id == request_id))).scalar_one_or_none()
    if not r or r.buyer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    if not payload.get("text"):
        raise HTTPException(status_code=400, detail="Пустое сообщение")
    db.add(CustomMessage(request_id=r.id, sender_id=current_user.id, text=payload["text"],
                         attachments=json.dumps(payload.get("attachments") or [])))
    shop = (await db.execute(select(Shop).where(Shop.id == r.shop_id))).scalar_one_or_none()
    await db.commit()
    if shop:
        await _notify(db, shop.owner_id, "Сообщение по запросу", r.title, "/seller/custom-requests")
        await db.commit()
    return {"ok": True}


@buyer_router.post("/{request_id}/accept")
async def accept_offer(request_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    r = (await db.execute(select(CustomRequest).where(CustomRequest.id == request_id))).scalar_one_or_none()
    if not r or r.buyer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    if r.status != CustomRequestStatus.quoted:
        raise HTTPException(status_code=400, detail="Нет активной оферты для принятия")
    r.status = CustomRequestStatus.accepted
    shop = (await db.execute(select(Shop).where(Shop.id == r.shop_id))).scalar_one_or_none()
    await db.commit()
    if shop:
        await _notify(db, shop.owner_id, "Оферта принята", f"{r.title}: покупатель принял условия", "/seller/custom-requests")
        await db.commit()
    return _req_dict(r)


@buyer_router.post("/{request_id}/cancel")
async def cancel_request(request_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    r = (await db.execute(select(CustomRequest).where(CustomRequest.id == request_id))).scalar_one_or_none()
    if not r or r.buyer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    if r.status in (CustomRequestStatus.completed, CustomRequestStatus.cancelled):
        raise HTTPException(status_code=400, detail="Запрос уже закрыт")
    r.status = CustomRequestStatus.cancelled
    await db.commit()
    return _req_dict(r)


# ─── Seller ─────────────────────────────────────────────────────────────────────

@seller_router.get("")
async def shop_requests(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_seller)):
    shop_id = await _seller_shop_id(db, current_user)
    rows = (await db.execute(
        select(CustomRequest).where(CustomRequest.shop_id == shop_id).order_by(CustomRequest.created_at.desc())
    )).scalars().all()
    return [_req_dict(r) for r in rows]


async def _seller_request(db: AsyncSession, request_id: int, current_user: User) -> CustomRequest:
    shop_id = await _seller_shop_id(db, current_user)
    r = (await db.execute(
        select(CustomRequest).options(selectinload(CustomRequest.messages)).where(CustomRequest.id == request_id)
    )).scalar_one_or_none()
    if not r or r.shop_id != shop_id:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    return r


@seller_router.get("/{request_id}")
async def get_request_seller(request_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_seller)):
    return _req_dict(await _seller_request(db, request_id, current_user), messages=True)


@seller_router.post("/{request_id}/message")
async def seller_message(request_id: int, payload: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_seller)):
    r = await _seller_request(db, request_id, current_user)
    if not payload.get("text"):
        raise HTTPException(status_code=400, detail="Пустое сообщение")
    db.add(CustomMessage(request_id=r.id, sender_id=current_user.id, text=payload["text"],
                         attachments=json.dumps(payload.get("attachments") or [])))
    await db.commit()
    await _notify(db, r.buyer_id, "Сообщение по вашему запросу", r.title, "/custom-requests")
    await db.commit()
    return {"ok": True}


@seller_router.post("/{request_id}/offer")
async def send_offer(request_id: int, payload: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_seller)):
    r = await _seller_request(db, request_id, current_user)
    if r.status in (CustomRequestStatus.completed, CustomRequestStatus.cancelled, CustomRequestStatus.declined):
        raise HTTPException(status_code=400, detail="Запрос закрыт")
    price = payload.get("price")
    if price is None:
        raise HTTPException(status_code=400, detail="Укажите цену")
    from decimal import Decimal
    r.quoted_price = Decimal(str(price))
    r.quoted_days = payload.get("days")
    r.deposit_percent = Decimal(str(payload["deposit_percent"])) if payload.get("deposit_percent") is not None else None
    r.offer_note = payload.get("note")
    r.status = CustomRequestStatus.quoted
    await db.commit()
    await _notify(db, r.buyer_id, "Получена оферта на изготовление", f"{r.title}: {r.quoted_price} ₽", "/custom-requests")
    await db.commit()
    return _req_dict(r)


@seller_router.post("/{request_id}/status")
async def update_status(request_id: int, payload: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_seller)):
    r = await _seller_request(db, request_id, current_user)
    new = payload.get("status")
    allowed = {"in_production", "ready", "completed"}
    if new not in allowed:
        raise HTTPException(status_code=400, detail="Недопустимый статус")
    if r.status not in (CustomRequestStatus.accepted, CustomRequestStatus.in_production, CustomRequestStatus.ready):
        raise HTTPException(status_code=400, detail="Сначала покупатель должен принять оферту")
    r.status = CustomRequestStatus(new)
    await db.commit()
    await _notify(db, r.buyer_id, "Статус изготовления обновлён", f"{r.title}: {new}", "/custom-requests")
    await db.commit()
    return _req_dict(r)


@seller_router.post("/{request_id}/decline")
async def decline_request(request_id: int, payload: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_seller)):
    r = await _seller_request(db, request_id, current_user)
    if r.status in (CustomRequestStatus.completed, CustomRequestStatus.cancelled):
        raise HTTPException(status_code=400, detail="Запрос уже закрыт")
    r.status = CustomRequestStatus.declined
    r.offer_note = payload.get("reason") or r.offer_note
    await db.commit()
    await _notify(db, r.buyer_id, "Запрос отклонён", r.title, "/custom-requests")
    await db.commit()
    return _req_dict(r)

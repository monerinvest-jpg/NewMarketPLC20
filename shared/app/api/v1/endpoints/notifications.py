"""
Block 2 endpoints: in-app notifications and buyer-seller chat.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.models import (
    ChatMessage, ChatThread, Notification, NotificationType, Shop, User,
)
from app.schemas.schemas import (
    ChatMessageCreate, ChatMessageOut, ChatThreadOut,
    NotificationOut, StartChatRequest,
)
from app.services.notification_service import notify

router = APIRouter(tags=["notifications-chat"])


# ─── Notifications ───────────────────────────────────────────────────────────────

@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    unread_only: bool = Query(False),
):
    query = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        query = query.where(Notification.is_read == False)  # noqa: E712
    query = query.order_by(Notification.created_at.desc()).limit(50)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/notifications/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
    )
    return {"count": result.scalar_one()}


@router.post("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    n = result.scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    n.is_read = True
    await db.commit()
    return {"status": "ok"}


@router.post("/notifications/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    await db.commit()
    return {"status": "ok"}


# ─── Chat ────────────────────────────────────────────────────────────────────────

async def _user_in_thread(thread: ChatThread, user: User, db: AsyncSession) -> bool:
    if thread.buyer_id == user.id:
        return True
    shop_result = await db.execute(select(Shop).where(Shop.id == thread.shop_id))
    shop = shop_result.scalar_one_or_none()
    return bool(shop and shop.owner_id == user.id)


@router.get("/chat/threads", response_model=list[dict])
async def list_threads(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Threads where the user is the buyer OR owns the shop. Returns lightweight
    thread info with the other party's name and last message preview.
    """
    # Buyer side
    buyer_threads = (await db.execute(
        select(ChatThread).where(ChatThread.buyer_id == current_user.id)
    )).scalars().all()

    # Seller side: threads for the user's shop
    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    seller_threads = []
    if shop:
        seller_threads = (await db.execute(
            select(ChatThread).where(ChatThread.shop_id == shop.id)
        )).scalars().all()

    threads = {t.id: t for t in [*buyer_threads, *seller_threads]}.values()

    out = []
    for t in sorted(threads, key=lambda x: x.updated_at, reverse=True):
        last = (await db.execute(
            select(ChatMessage).where(ChatMessage.thread_id == t.id)
            .order_by(ChatMessage.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        shop_obj = (await db.execute(select(Shop).where(Shop.id == t.shop_id))).scalar_one_or_none()
        buyer_obj = (await db.execute(select(User).where(User.id == t.buyer_id))).scalar_one_or_none()
        is_seller_view = bool(shop and t.shop_id == shop.id)
        other_name = (buyer_obj.full_name if is_seller_view else (shop_obj.name if shop_obj else "Магазин"))
        unread = (await db.execute(
            select(func.count()).select_from(ChatMessage).where(
                ChatMessage.thread_id == t.id,
                ChatMessage.sender_id != current_user.id,
                ChatMessage.is_read == False,  # noqa: E712
            )
        )).scalar_one()
        out.append({
            "id": t.id, "shop_id": t.shop_id, "buyer_id": t.buyer_id,
            "other_name": other_name, "is_seller_view": is_seller_view,
            "last_message": last.text[:80] if last else None,
            "updated_at": t.updated_at.isoformat(), "unread": unread,
        })
    return out


@router.get("/chat/threads/{thread_id}/messages", response_model=list[ChatMessageOut])
async def get_messages(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = (await db.execute(select(ChatThread).where(ChatThread.id == thread_id))).scalar_one_or_none()
    if not thread or not await _user_in_thread(thread, current_user, db):
        raise HTTPException(status_code=404, detail="Диалог не найден")

    # Mark incoming messages as read
    await db.execute(
        update(ChatMessage)
        .where(ChatMessage.thread_id == thread_id, ChatMessage.sender_id != current_user.id)
        .values(is_read=True)
    )
    await db.commit()

    result = await db.execute(
        select(ChatMessage).where(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at)
    )
    return result.scalars().all()


@router.post("/chat/start", response_model=ChatThreadOut, status_code=201)
async def start_chat(
    payload: StartChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Buyer opens (or reuses) a thread with a shop and sends the first message."""
    shop = (await db.execute(select(Shop).where(Shop.id == payload.shop_id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    if shop.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя написать самому себе")

    thread = (await db.execute(
        select(ChatThread).where(
            ChatThread.buyer_id == current_user.id, ChatThread.shop_id == payload.shop_id
        )
    )).scalar_one_or_none()
    if not thread:
        thread = ChatThread(buyer_id=current_user.id, shop_id=payload.shop_id)
        db.add(thread)
        await db.flush()

    msg = ChatMessage(thread_id=thread.id, sender_id=current_user.id, text=payload.text)
    db.add(msg)
    thread.updated_at = datetime.now(timezone.utc)

    await notify(
        db, shop.owner_id, NotificationType.new_message,
        title="Новое сообщение от покупателя", body=payload.text[:120], link="/chat",
    )
    await db.commit()
    await db.refresh(thread)
    return thread


@router.post("/chat/threads/{thread_id}/messages", response_model=ChatMessageOut, status_code=201)
async def send_message(
    thread_id: int,
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = (await db.execute(select(ChatThread).where(ChatThread.id == thread_id))).scalar_one_or_none()
    if not thread or not await _user_in_thread(thread, current_user, db):
        raise HTTPException(status_code=404, detail="Диалог не найден")

    msg = ChatMessage(thread_id=thread_id, sender_id=current_user.id, text=payload.text)
    db.add(msg)
    thread.updated_at = datetime.now(timezone.utc)

    # Notify the other party
    shop = (await db.execute(select(Shop).where(Shop.id == thread.shop_id))).scalar_one_or_none()
    if shop:
        recipient_id = thread.buyer_id if current_user.id == shop.owner_id else shop.owner_id
        await notify(
            db, recipient_id, NotificationType.new_message,
            title="Новое сообщение", body=payload.text[:120], link="/chat",
        )

    await db.commit()
    await db.refresh(msg)
    return msg

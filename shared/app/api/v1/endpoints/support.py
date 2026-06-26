"""
Support tickets: a chat-style help desk between users and support staff.

- Any authenticated user can open tickets and message support.
- Support agents (UserRole.support), moderators and superadmins work the queue,
  assign tickets, reply, change status/priority, and read user/seller data.
- Moderators lead support (support.manage) and see statistics.
- Superadmins can do everything, including editing users via the admin module.
"""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_user, get_current_support_staff
from app.core.database import get_db
from app.models.models import (
    NotificationType, Order, Shop, SupportMessage, SupportTicket,
    SupportTicketPriority, SupportTicketStatus, User, UserRole,
)
from app.schemas.schemas import (
    SupportMessageCreate, SupportMessageOut, SupportStats, SupportTicketCreate,
    SupportTicketDetailOut, SupportTicketOut, SupportTicketUpdate, SupportUserView,
)
from app.services.notification_service import notify
from app.services import support_service

router = APIRouter(prefix="/support", tags=["support"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────── User-facing ───────────────────────────

@router.post("/tickets", response_model=SupportTicketDetailOut)
async def create_ticket(
    payload: SupportTicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=payload.subject,
        category=payload.category,
        priority=payload.priority or SupportTicketPriority.normal,
        status=SupportTicketStatus.open,
        last_message_at=_now(),
    )
    db.add(ticket)
    await db.flush()
    db.add(SupportMessage(
        ticket_id=ticket.id, sender_id=current_user.id, is_staff=False,
        text=payload.message, read_by_user=True,
    ))
    await db.commit()
    return await _load_detail(db, ticket.id)


@router.get("/tickets", response_model=list[SupportTicketOut])
async def my_tickets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(SupportTicket).where(SupportTicket.user_id == current_user.id)
        .order_by(SupportTicket.last_message_at.desc())
    )).scalars().all()
    return list(rows)


@router.get("/tickets/{ticket_id}", response_model=SupportTicketDetailOut)
async def get_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await _load_detail(db, ticket_id)
    if ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    # Mark staff messages as read by the user.
    await db.execute(
        SupportMessage.__table__.update()
        .where(SupportMessage.ticket_id == ticket_id, SupportMessage.is_staff == True)  # noqa: E712
        .values(read_by_user=True)
    )
    await db.commit()
    return ticket


@router.post("/tickets/{ticket_id}/messages", response_model=SupportMessageOut)
async def add_user_message(
    ticket_id: int,
    payload: SupportMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = (await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )).scalar_one_or_none()
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status == SupportTicketStatus.closed:
        raise HTTPException(status_code=400, detail="Обращение закрыто")

    msg = SupportMessage(
        ticket_id=ticket_id, sender_id=current_user.id, is_staff=False,
        text=payload.text, attachment_url=payload.attachment_url, read_by_user=True,
    )
    db.add(msg)
    ticket.last_message_at = _now()
    # A user reply reopens a resolved/pending ticket for the agents.
    if ticket.status in (SupportTicketStatus.resolved, SupportTicketStatus.pending_user):
        ticket.status = SupportTicketStatus.open
    await db.commit()
    await db.refresh(msg)
    return msg


@router.post("/tickets/{ticket_id}/close", response_model=SupportTicketOut)
async def close_my_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = (await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )).scalar_one_or_none()
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.status = SupportTicketStatus.closed
    ticket.closed_at = _now()
    await db.commit()
    await db.refresh(ticket)
    return ticket


# ─────────────────────────── Staff-facing ───────────────────────────

@router.get("/staff/tickets", response_model=dict)
async def staff_list_tickets(
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    assigned: str | None = Query(None, description="me | unassigned | <user_id>"),
    priority: str | None = None,
    q: str | None = None,
    overdue: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    me: User = Depends(get_current_support_staff),
):
    query = select(SupportTicket)
    if status_filter:
        try:
            query = query.where(SupportTicket.status == SupportTicketStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail="Недопустимый статус")
    if priority:
        try:
            query = query.where(SupportTicket.priority == SupportTicketPriority(priority))
        except ValueError:
            raise HTTPException(status_code=400, detail="Недопустимый приоритет")
    if overdue:
        from datetime import timedelta
        from app.core.config import settings as _s
        threshold = _now() - timedelta(hours=_s.SUPPORT_SLA_FIRST_RESPONSE_HOURS)
        query = query.where(
            SupportTicket.first_response_at.is_(None),
            SupportTicket.created_at < threshold,
            SupportTicket.status.in_([SupportTicketStatus.open, SupportTicketStatus.in_progress]),
        )
    if assigned == "me":
        query = query.where(SupportTicket.assigned_to_id == me.id)
    elif assigned == "unassigned":
        query = query.where(SupportTicket.assigned_to_id.is_(None))
    elif assigned and assigned.isdigit():
        query = query.where(SupportTicket.assigned_to_id == int(assigned))
    if q:
        query = query.where(SupportTicket.subject.ilike(f"%{q}%"))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(
        query.order_by(SupportTicket.last_message_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {
        "items": [SupportTicketOut.model_validate(t).model_dump(mode="json") for t in rows],
        "total": total, "page": page, "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.get("/staff/tickets/{ticket_id}", response_model=SupportTicketDetailOut)
async def staff_get_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_support_staff),
):
    ticket = await _load_detail(db, ticket_id)
    # Mark user messages as read by staff.
    await db.execute(
        SupportMessage.__table__.update()
        .where(SupportMessage.ticket_id == ticket_id, SupportMessage.is_staff == False)  # noqa: E712
        .values(read_by_staff=True)
    )
    await db.commit()
    return ticket


@router.post("/staff/tickets/{ticket_id}/reply", response_model=SupportMessageOut)
async def staff_reply(
    ticket_id: int,
    payload: SupportMessageCreate,
    db: AsyncSession = Depends(get_db),
    me: User = Depends(get_current_support_staff),
):
    ticket = (await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msg = SupportMessage(
        ticket_id=ticket_id, sender_id=me.id, is_staff=True,
        text=payload.text, attachment_url=payload.attachment_url, read_by_staff=True,
    )
    db.add(msg)
    now = _now()
    ticket.last_message_at = now
    if ticket.first_response_at is None:
        ticket.first_response_at = now
    # Replying takes ownership and moves the ticket into progress.
    if ticket.assigned_to_id is None:
        ticket.assigned_to_id = me.id
    if ticket.status in (SupportTicketStatus.open,):
        ticket.status = SupportTicketStatus.in_progress
    await db.commit()
    await db.refresh(msg)

    await notify(
        db, ticket.user_id, NotificationType.system,
        title="Ответ поддержки",
        body=f"По обращению «{ticket.subject}» есть ответ.",
        link=f"/support/{ticket.id}",
    )
    return msg


@router.patch("/staff/tickets/{ticket_id}", response_model=SupportTicketOut)
async def staff_update_ticket(
    ticket_id: int,
    payload: SupportTicketUpdate,
    db: AsyncSession = Depends(get_db),
    me: User = Depends(get_current_support_staff),
):
    ticket = (await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Assignment to a different agent is a "manage" action; restrict to
    # moderators/superadmins (support.manage). Self-assign is always allowed.
    if payload.assigned_to_id is not None and payload.assigned_to_id != me.id:
        from app.services.rbac_service import has_permission
        if not has_permission(me, "support.manage"):
            raise HTTPException(status_code=403, detail="Назначение на другого агента доступно руководителю поддержки")
        ticket.assigned_to_id = payload.assigned_to_id
    elif payload.assigned_to_id is not None:
        ticket.assigned_to_id = payload.assigned_to_id

    if payload.priority is not None:
        ticket.priority = payload.priority
    if payload.status is not None:
        ticket.status = payload.status
        if payload.status == SupportTicketStatus.closed:
            ticket.closed_at = _now()
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.post("/staff/tickets/{ticket_id}/assign-me", response_model=SupportTicketOut)
async def staff_assign_me(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    me: User = Depends(get_current_support_staff),
):
    ticket = (await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.assigned_to_id = me.id
    if ticket.status == SupportTicketStatus.open:
        ticket.status = SupportTicketStatus.in_progress
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.get("/staff/stats", response_model=SupportStats)
async def staff_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_support_staff),
):
    async def count(*conds) -> int:
        return (await db.execute(
            select(func.count()).select_from(SupportTicket).where(*conds)
        )).scalar_one()

    start_of_today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    by_priority = {}
    for p in SupportTicketPriority:
        by_priority[p.value] = await count(SupportTicket.priority == p)

    # Average first-response time (minutes) over tickets that got a reply.
    rows = (await db.execute(
        select(SupportTicket.created_at, SupportTicket.first_response_at)
        .where(SupportTicket.first_response_at.is_not(None))
    )).all()
    if rows:
        total_min = sum((fr - cr).total_seconds() / 60 for cr, fr in rows)
        avg_first = round(total_min / len(rows), 1)
    else:
        avg_first = None

    return SupportStats(
        open=await count(SupportTicket.status == SupportTicketStatus.open),
        in_progress=await count(SupportTicket.status == SupportTicketStatus.in_progress),
        pending_user=await count(SupportTicket.status == SupportTicketStatus.pending_user),
        resolved_today=await count(
            SupportTicket.status == SupportTicketStatus.resolved,
            SupportTicket.updated_at >= start_of_today,
        ),
        closed=await count(SupportTicket.status == SupportTicketStatus.closed),
        unassigned=await count(SupportTicket.assigned_to_id.is_(None),
                               SupportTicket.status != SupportTicketStatus.closed),
        overdue=await support_service.overdue_count(db),
        avg_first_response_minutes=avg_first,
        by_priority=by_priority,
    )


@router.post("/staff/sla-sweep")
async def run_sla_sweep(
    db: AsyncSession = Depends(get_db),
    me: User = Depends(get_current_support_staff),
):
    """Run the SLA sweep now: escalate overdue tickets and auto-assign unowned
    ones. Restricted to support leads (support.manage)."""
    from app.services.rbac_service import has_permission
    if not has_permission(me, "support.manage"):
        raise HTTPException(status_code=403, detail="Доступно руководителю поддержки")
    result = await support_service.sla_sweep(db)
    await db.commit()
    return result


@router.get("/staff/users/{user_id}", response_model=SupportUserView)
async def staff_user_view(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_support_staff),
):
    """Read-only 360° view of a user/seller for support & moderators. Editing is
    a superadmin action handled by the admin module."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    orders_count = (await db.execute(
        select(func.count()).select_from(Order).where(Order.buyer_id == user_id)
    )).scalar_one()
    tickets_count = (await db.execute(
        select(func.count()).select_from(SupportTicket).where(SupportTicket.user_id == user_id)
    )).scalar_one()
    shop = (await db.execute(select(Shop).where(Shop.owner_id == user_id))).scalar_one_or_none()

    return SupportUserView(
        id=user.id, email=user.email, full_name=user.full_name, phone=user.phone,
        role=user.role, is_active=user.is_active, balance=user.balance,
        bonus_balance=user.bonus_balance, created_at=user.created_at,
        orders_count=orders_count, tickets_count=tickets_count,
        is_seller=shop is not None,
        shop_id=shop.id if shop else None, shop_name=shop.name if shop else None,
    )


# ─────────────────────────── helpers ───────────────────────────

async def _load_detail(db: AsyncSession, ticket_id: int) -> SupportTicket:
    ticket = (await db.execute(
        select(SupportTicket)
        .options(
            selectinload(SupportTicket.messages),
            selectinload(SupportTicket.user),
            selectinload(SupportTicket.assigned_to),
        )
        .where(SupportTicket.id == ticket_id)
    )).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

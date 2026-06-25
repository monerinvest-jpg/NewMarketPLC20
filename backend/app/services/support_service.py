"""
Support SLA automation.

`sla_sweep` runs periodically (Celery) and on demand. For tickets that have
waited past the first-response SLA without a staff reply it:
  - escalates the priority one level (low→normal→high→urgent), once per sweep,
    tracked by `escalation_level` so it never double-escalates the same step;
  - auto-assigns unassigned overdue tickets to the least-loaded active support
    agent (when SUPPORT_AUTO_ASSIGN is on) and notifies that agent.

This keeps urgent, neglected tickets from sitting unowned in the queue.
"""
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    NotificationType, SupportTicket, SupportTicketPriority, SupportTicketStatus, User, UserRole,
)
from app.services.notification_service import notify

# Priority ladder used for escalation.
_PRIORITY_ORDER = [
    SupportTicketPriority.low,
    SupportTicketPriority.normal,
    SupportTicketPriority.high,
    SupportTicketPriority.urgent,
]


def _bump(priority: SupportTicketPriority) -> SupportTicketPriority:
    idx = _PRIORITY_ORDER.index(priority)
    return _PRIORITY_ORDER[min(idx + 1, len(_PRIORITY_ORDER) - 1)]


async def _least_loaded_agent(db: AsyncSession) -> User | None:
    """Active support agent with the fewest open/in-progress tickets."""
    agents = (await db.execute(
        select(User).where(User.role == UserRole.support, User.is_active == True)  # noqa: E712
    )).scalars().all()
    if not agents:
        return None
    best, best_load = None, None
    for a in agents:
        load = (await db.execute(
            select(func.count()).select_from(SupportTicket).where(
                SupportTicket.assigned_to_id == a.id,
                SupportTicket.status.in_([SupportTicketStatus.open, SupportTicketStatus.in_progress]),
            )
        )).scalar_one()
        if best_load is None or load < best_load:
            best, best_load = a, load
    return best


async def sla_sweep(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(hours=settings.SUPPORT_SLA_FIRST_RESPONSE_HOURS)

    overdue = (await db.execute(
        select(SupportTicket).where(
            SupportTicket.status.in_([SupportTicketStatus.open, SupportTicketStatus.in_progress]),
            SupportTicket.first_response_at.is_(None),
            SupportTicket.created_at < threshold,
        )
    )).scalars().all()

    escalated, assigned = 0, 0
    for ticket in overdue:
        # Escalate one priority level per sweep until urgent.
        if ticket.priority != SupportTicketPriority.urgent:
            ticket.priority = _bump(ticket.priority)
            ticket.escalation_level += 1
            escalated += 1

        # Auto-assign if unowned.
        if settings.SUPPORT_AUTO_ASSIGN and ticket.assigned_to_id is None:
            agent = await _least_loaded_agent(db)
            if agent is not None:
                ticket.assigned_to_id = agent.id
                assigned += 1
                await notify(
                    db, agent.id, NotificationType.system,
                    title="Просроченное обращение назначено вам",
                    body=f"Обращение #{ticket.id}: «{ticket.subject}» ждёт ответа дольше SLA.",
                    link="/support-desk",
                )

    return {"overdue": len(overdue), "escalated": escalated, "auto_assigned": assigned}


async def overdue_count(db: AsyncSession) -> int:
    threshold = datetime.now(timezone.utc) - timedelta(hours=settings.SUPPORT_SLA_FIRST_RESPONSE_HOURS)
    return (await db.execute(
        select(func.count()).select_from(SupportTicket).where(
            SupportTicket.status.in_([SupportTicketStatus.open, SupportTicketStatus.in_progress]),
            SupportTicket.first_response_at.is_(None),
            SupportTicket.created_at < threshold,
        )
    )).scalar_one()

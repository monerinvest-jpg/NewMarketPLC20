"""
Audit log service. Records significant staff/system actions (moderation,
payouts, role changes, settings edits) for accountability. Append-only;
callers add within their own transaction and commit as usual.
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditLog


async def log_action(
    db: AsyncSession,
    actor_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    detail: Optional[str] = None,
) -> AuditLog:
    """Append an audit record. Caller is responsible for commit."""
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
    )
    db.add(entry)
    return entry

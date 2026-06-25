"""
Notification service. Central helper used across the app to create in-app
notifications (the bell menu). Kept side-effect-light: callers add the
notification within their own transaction and commit as usual.

When send_email=True and the recipient has email notifications enabled, the
notification is also dispatched by email (best-effort; failures never block).
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Notification, NotificationType, User


async def notify(
    db: AsyncSession,
    user_id: int,
    type: NotificationType,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    send_email: bool = False,
    send_sms: bool = False,
) -> Notification:
    """Create a notification for a user. Caller is responsible for commit."""
    n = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link=link,
    )
    db.add(n)

    if send_email:
        try:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if user and getattr(user, "email_notifications", True) and user.email:
                from app.services.email_service import send_email as _send
                await _send(
                    to=user.email,
                    subject=title,
                    body=(body or title) + (f"\n\n{link}" if link else ""),
                )
        except Exception:
            pass

    if send_sms:
        # Only sends if SMS is globally enabled AND the order-status SMS toggle is
        # on AND the user has a verified phone. All gated inside the sms_service.
        try:
            from app.services.sms_service import is_enabled as sms_is_enabled, send_sms as _sms
            from app.services.settings_service import get_setting
            if await sms_is_enabled(db) and (await get_setting(db, "sms_notify_order_status")).lower() == "true":
                user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                if user and user.phone and user.phone_verified:
                    await _sms(db, user.phone, f"{title}. {body or ''}".strip()[:300], purpose="order_status")
        except Exception:
            pass

    return n

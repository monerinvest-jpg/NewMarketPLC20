"""
Marketing campaigns: resolve a user segment and broadcast over email or in-app
notifications. Email sends include a one-click unsubscribe link (HMAC-signed),
and opted-out / inactive users are always excluded.
"""
import base64
import hashlib
import hmac
import json
from datetime import timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    Campaign, CampaignChannel, CampaignStatus, Order, User, utcnow,
)

BATCH = 200


def _segment_query(seg: dict):
    """Build a User query from a segment filter. Always excludes inactive and
    opted-out users."""
    q = select(User).where(User.is_active == True, User.marketing_opt_out == False)  # noqa: E712
    if seg.get("role"):
        q = q.where(User.role == seg["role"])
    if seg.get("only_verified_email"):
        q = q.where(User.email_verified == True)  # noqa: E712
    if seg.get("has_referral_balance"):
        q = q.where(User.referral_balance > 0)
    days = seg.get("active_within_days")
    if days:
        cutoff = utcnow() - timedelta(days=int(days))
        q = q.where(User.id.in_(select(Order.buyer_id).where(Order.created_at >= cutoff)))
    return q


async def preview_count(db: AsyncSession, seg: dict) -> int:
    sub = _segment_query(seg).subquery()
    return (await db.execute(select(func.count()).select_from(sub))).scalar_one()


# ── Unsubscribe tokens (HMAC over user id; no DB token storage needed) ──────────

def make_unsub_token(user_id: int) -> str:
    raw = str(user_id).encode()
    sig = hmac.new(settings.SECRET_KEY.encode(), raw, hashlib.sha256).hexdigest()[:16]
    return base64.urlsafe_b64encode(f"{user_id}.{sig}".encode()).decode()


def verify_unsub_token(token: str) -> Optional[int]:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        uid_str, sig = decoded.rsplit(".", 1)
        expected = hmac.new(settings.SECRET_KEY.encode(), uid_str.encode(), hashlib.sha256).hexdigest()[:16]
        if hmac.compare_digest(sig, expected):
            return int(uid_str)
    except Exception:  # noqa: BLE001
        return None
    return None


async def send_campaign(db: AsyncSession, campaign: Campaign) -> int:
    """Resolve the segment and deliver the campaign. Updates status + counts.
    Best-effort per recipient; failures don't abort the whole run."""
    from app.services.email_service import send_email, _wrap_html
    from app.services.notification_service import notify
    from app.models.models import NotificationType

    seg = json.loads(campaign.segment) if campaign.segment else {}
    campaign.status = CampaignStatus.sending
    await db.commit()

    sent = 0
    offset = 0
    while True:
        rows = (await db.execute(
            _segment_query(seg).order_by(User.id).offset(offset).limit(BATCH)
        )).scalars().all()
        if not rows:
            break
        for user in rows:
            try:
                if campaign.channel == CampaignChannel.email:
                    unsub = f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/users/unsubscribe?token={make_unsub_token(user.id)}"
                    lines = [campaign.body]
                    if campaign.link:
                        lines.append(f'<a href="{campaign.link}">Перейти</a>')
                    lines.append(f'<span style="font-size:12px;color:#999">Отписаться: <a href="{unsub}">ссылка</a></span>')
                    html = _wrap_html(campaign.subject or campaign.title, lines)
                    await send_email(user.email, campaign.subject or campaign.title, campaign.body, html)
                else:
                    await notify(
                        db, user.id, NotificationType.system,
                        title=campaign.subject or campaign.title,
                        body=campaign.body, link=campaign.link or "/", send_email=False,
                    )
                sent += 1
            except Exception:  # noqa: BLE001 — one bad recipient never aborts the run
                pass
        offset += BATCH
        await db.commit()

    campaign.sent_count = sent
    campaign.status = CampaignStatus.sent
    campaign.sent_at = utcnow()
    await db.commit()
    return sent

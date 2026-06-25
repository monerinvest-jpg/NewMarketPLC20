"""
Verification service. Generates short numeric codes for confirming email or
phone, stores them with an expiry, and checks submitted codes. A new code for
the same (user, purpose) invalidates older unused ones.
"""
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User, VerificationCode, VerificationPurpose

CODE_TTL_MINUTES = 15
MAX_ATTEMPTS = 5


def _generate_code() -> str:
    """A 6-digit numeric code."""
    return f"{secrets.randbelow(1000000):06d}"


async def issue_code(
    db: AsyncSession,
    user: User,
    purpose: VerificationPurpose,
    destination: str,
) -> str:
    """
    Create a fresh code, invalidating older unused codes for the same purpose.
    Returns the plain code so the caller can send it. Caller commits.
    """
    # Invalidate previous unused codes
    await db.execute(
        update(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.purpose == purpose,
            VerificationCode.used == False,  # noqa: E712
        )
        .values(used=True)
    )
    code = _generate_code()
    entry = VerificationCode(
        user_id=user.id,
        code=code,
        purpose=purpose,
        destination=destination,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES),
        used=False,
        attempts=0,
    )
    db.add(entry)
    return code


async def verify_code(
    db: AsyncSession,
    user: User,
    purpose: VerificationPurpose,
    submitted: str,
) -> tuple[bool, Optional[str]]:
    """
    Check a submitted code. Returns (ok, error_message). On success the code is
    marked used and the relevant *_verified flag is set on the user. Caller commits.
    """
    entry = (await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.purpose == purpose,
            VerificationCode.used == False,  # noqa: E712
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if not entry:
        return False, "Код не найден. Запросите новый."
    if entry.attempts >= MAX_ATTEMPTS:
        entry.used = True
        return False, "Слишком много попыток. Запросите новый код."

    now = datetime.now(timezone.utc)
    expires = entry.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        entry.used = True
        return False, "Срок действия кода истёк. Запросите новый."

    entry.attempts += 1
    if entry.code != submitted.strip():
        return False, "Неверный код."

    entry.used = True
    if purpose == VerificationPurpose.email:
        user.email_verified = True
    elif purpose == VerificationPurpose.phone:
        user.phone_verified = True
    return True, None

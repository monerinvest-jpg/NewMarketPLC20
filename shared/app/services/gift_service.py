"""
Gift certificates & promo balance.

A gift certificate is a code worth a fixed amount. It can be purchased by a buyer
(funded from their main balance) or issued by an admin for promos. Redeeming a
code credits the redeemer's promo balance, which is spent automatically at
checkout alongside bonuses.
"""
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    BalanceTransaction, BalanceTransactionType, GiftCertificate, GiftCertificateStatus,
    PromoBalanceTransaction, User,
)

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous chars


def _gen_code() -> str:
    block = lambda: "".join(secrets.choice(_ALPHABET) for _ in range(4))
    return f"GIFT-{block()}-{block()}"


async def _unique_code(db: AsyncSession) -> str:
    for _ in range(10):
        code = _gen_code()
        exists = (await db.execute(
            select(GiftCertificate.id).where(GiftCertificate.code == code)
        )).scalar_one_or_none()
        if not exists:
            return code
    raise RuntimeError("Не удалось сгенерировать уникальный код")


async def purchase(
    db: AsyncSession, buyer: User, amount: Decimal,
    recipient_email: Optional[str] = None, message: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> GiftCertificate:
    """Buy a gift certificate, funded from the buyer's main balance."""
    if amount <= 0:
        raise ValueError("Сумма должна быть положительной")
    if buyer.balance < amount:
        raise ValueError("Недостаточно средств на балансе")
    buyer.balance -= amount
    db.add(BalanceTransaction(
        user_id=buyer.id, change=-amount, type=BalanceTransactionType.debit,
        reference_type="gift_certificate", description="Покупка подарочного сертификата",
        balance_after=buyer.balance,
    ))
    cert = GiftCertificate(
        code=await _unique_code(db), amount=amount, purchaser_id=buyer.id,
        recipient_email=recipient_email, message=message, expires_at=expires_at,
    )
    db.add(cert)
    await db.flush()

    # If gifted to someone, email them the code (best-effort; never blocks purchase).
    if recipient_email:
        try:
            from app.core.config import settings
            from app.services.email_service import send_email, _wrap_html
            link = f"{settings.FRONTEND_URL.rstrip('/')}/gift-certificates"
            lines = [
                f"<b>{buyer.full_name}</b> дарит вам подарочный сертификат на <b>{amount} ₽</b>.",
            ]
            if message:
                lines.append(f"«{message}»")
            lines.append(f"Ваш код: <span style='font-size:22px;font-weight:700;letter-spacing:2px;color:#7c4a21'>{cert.code}</span>")
            lines.append("Активируйте его в личном кабинете — баланс зачислится на промо-счёт.")
            html = _wrap_html("Вам подарок 🎁", lines, cta=("Активировать сертификат", link))
            await send_email(recipient_email, "Вам подарили сертификат 🎁",
                             f"{buyer.full_name} дарит вам сертификат на {amount} ₽. Код: {cert.code}", html)
        except Exception:  # noqa: BLE001
            pass
    return cert


async def issue(
    db: AsyncSession, amount: Decimal, count: int = 1,
    expires_at: Optional[datetime] = None, message: Optional[str] = None,
) -> list[GiftCertificate]:
    """Admin: issue promo certificates (no charge)."""
    out = []
    for _ in range(max(1, count)):
        cert = GiftCertificate(
            code=await _unique_code(db), amount=amount,
            expires_at=expires_at, message=message,
        )
        db.add(cert)
        out.append(cert)
    await db.flush()
    return out


async def redeem(db: AsyncSession, user: User, code: str) -> Decimal:
    """Redeem a code into the user's promo balance. Returns the credited amount."""
    cert = (await db.execute(
        select(GiftCertificate).where(GiftCertificate.code == code.strip().upper())
    )).scalar_one_or_none()
    if not cert:
        raise ValueError("Сертификат не найден")
    if cert.status != GiftCertificateStatus.active:
        raise ValueError("Сертификат уже использован или недействителен")
    if cert.expires_at and cert.expires_at < datetime.now(timezone.utc):
        cert.status = GiftCertificateStatus.expired
        raise ValueError("Срок действия сертификата истёк")

    cert.status = GiftCertificateStatus.redeemed
    cert.redeemed_by_id = user.id
    cert.redeemed_at = datetime.now(timezone.utc)
    user.promo_balance = (user.promo_balance or Decimal("0.00")) + cert.amount
    db.add(PromoBalanceTransaction(
        user_id=user.id, change=cert.amount, kind="gift_redeem",
        description=f"Активация сертификата {cert.code}", balance_after=user.promo_balance,
    ))
    await db.flush()
    return cert.amount


async def spend_promo(
    db: AsyncSession, user: User, amount: Decimal, description: str
) -> Decimal:
    """Deduct up to `amount` from the user's promo balance. Returns amount spent."""
    available = user.promo_balance or Decimal("0.00")
    spend = min(available, amount)
    if spend <= 0:
        return Decimal("0.00")
    user.promo_balance = available - spend
    db.add(PromoBalanceTransaction(
        user_id=user.id, change=-spend, kind="order_spend",
        description=description, balance_after=user.promo_balance,
    ))
    return spend


async def overview(db: AsyncSession, user: User, limit: int = 20) -> dict:
    txns = (await db.execute(
        select(PromoBalanceTransaction).where(PromoBalanceTransaction.user_id == user.id)
        .order_by(PromoBalanceTransaction.created_at.desc()).limit(limit)
    )).scalars().all()
    purchased = (await db.execute(
        select(GiftCertificate).where(GiftCertificate.purchaser_id == user.id)
        .order_by(GiftCertificate.created_at.desc())
    )).scalars().all()
    return {
        "promo_balance": str(user.promo_balance or Decimal("0.00")),
        "transactions": [
            {"id": t.id, "change": str(t.change), "kind": t.kind,
             "description": t.description, "balance_after": str(t.balance_after),
             "created_at": t.created_at.isoformat()}
            for t in txns
        ],
        "purchased": [
            {"id": c.id, "code": c.code, "amount": str(c.amount),
             "status": c.status.value, "recipient_email": c.recipient_email,
             "created_at": c.created_at.isoformat()}
            for c in purchased
        ],
    }

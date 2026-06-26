"""
Dispute arbitration. A buyer (or seller) opens a dispute over an order; the
parties discuss; if unresolved it is escalated to a platform mediator
(support/moderator) who decides the outcome and any refund.

Refunds mirror return_service: the buyer is credited to their money balance and
the seller's balance is debited for the same amount.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    BalanceTransaction, BalanceTransactionType, Dispute, DisputeMessage,
    DisputeResolution, DisputeStatus, NotificationType, Order, Shop, Transaction,
    TransactionType, User,
)
from app.services.notification_service import notify


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def role_in_dispute(db: AsyncSession, dispute: Dispute, user: User) -> Optional[str]:
    """Return the user's role for this dispute: buyer | seller | mediator | None."""
    if user.id == dispute.buyer_id:
        return "buyer"
    shop = (await db.execute(select(Shop).where(Shop.id == dispute.shop_id))).scalar_one_or_none()
    if shop and shop.owner_id == user.id:
        return "seller"
    from app.services.rbac_service import has_permission
    from app.models.models import UserRole
    if user.role in (UserRole.support, UserRole.moderator, UserRole.superadmin) \
            or user.is_superuser or has_permission(user, "support.handle"):
        return "mediator"
    return None


async def add_message(db: AsyncSession, dispute: Dispute, sender: User, role: str, text: str) -> DisputeMessage:
    msg = DisputeMessage(
        dispute_id=dispute.id, sender_id=sender.id, sender_role=role, text=text,
    )
    db.add(msg)
    dispute.last_message_at = _now()
    await db.flush()
    return msg


async def open_dispute(
    db: AsyncSession, buyer: User, order: Order, shop_id: int,
    subject: str, reason: str, order_item_id: Optional[int] = None,
) -> Dispute:
    dispute = Dispute(
        order_id=order.id, order_item_id=order_item_id, buyer_id=buyer.id,
        shop_id=shop_id, opened_by="buyer", subject=subject, reason=reason,
        status=DisputeStatus.open, last_message_at=_now(),
    )
    db.add(dispute)
    await db.flush()
    db.add(DisputeMessage(
        dispute_id=dispute.id, sender_id=buyer.id, sender_role="buyer", text=reason,
    ))
    # Notify the seller.
    shop = (await db.execute(select(Shop).where(Shop.id == shop_id))).scalar_one_or_none()
    if shop:
        await notify(
            db, shop.owner_id, NotificationType.system,
            title="Открыт спор по заказу",
            body=f"Покупатель открыл спор: «{subject}».",
            link="/seller/disputes",
        )
    await db.flush()
    return dispute


async def escalate(db: AsyncSession, dispute: Dispute) -> None:
    """Escalate to platform mediation."""
    dispute.status = DisputeStatus.in_mediation
    db.add(DisputeMessage(
        dispute_id=dispute.id, sender_id=dispute.buyer_id, sender_role="system",
        text="Спор передан на рассмотрение арбитражу платформы.",
    ))
    await db.flush()


async def _apply_refund(db: AsyncSession, dispute: Dispute, amount: Decimal) -> None:
    """Credit the buyer and debit the seller for a dispute refund."""
    if amount <= 0:
        return
    buyer = (await db.execute(select(User).where(User.id == dispute.buyer_id))).scalar_one_or_none()
    shop = (await db.execute(select(Shop).where(Shop.id == dispute.shop_id))).scalar_one_or_none()
    if buyer:
        buyer.balance += amount
        db.add(Transaction(
            user_id=buyer.id, type=TransactionType.order_refund, amount=amount,
            order_id=dispute.order_id, description=f"Возврат по спору #{dispute.id}",
            balance_after=buyer.balance,
        ))
    if shop:
        owner = (await db.execute(select(User).where(User.id == shop.owner_id))).scalar_one_or_none()
        if owner:
            owner.balance -= amount
            db.add(BalanceTransaction(
                user_id=owner.id, change=-amount, type=BalanceTransactionType.debit,
                reference_type="dispute", reference_id=dispute.id,
                description=f"Списание по спору #{dispute.id}", balance_after=owner.balance,
            ))


async def resolve(
    db: AsyncSession, dispute: Dispute, resolution: DisputeResolution,
    refund_amount: Optional[Decimal], note: Optional[str], actor: User,
) -> None:
    """Close a dispute with an outcome; apply a refund for buyer_favor/partial."""
    dispute.resolution = resolution
    dispute.resolution_note = note
    dispute.status = DisputeStatus.resolved
    dispute.resolved_at = _now()

    if resolution in (DisputeResolution.buyer_favor, DisputeResolution.partial):
        amount = refund_amount or Decimal("0.00")
        dispute.refund_amount = amount
        await _apply_refund(db, dispute, amount)

    outcome_text = {
        DisputeResolution.buyer_favor: "в пользу покупателя (возврат средств)",
        DisputeResolution.partial: "частичный возврат покупателю",
        DisputeResolution.seller_favor: "в пользу продавца",
        DisputeResolution.none: "без решения",
    }[resolution]
    db.add(DisputeMessage(
        dispute_id=dispute.id, sender_id=actor.id, sender_role="system",
        text=f"Спор закрыт: {outcome_text}." + (f" {note}" if note else ""),
    ))

    # Notify both sides.
    shop = (await db.execute(select(Shop).where(Shop.id == dispute.shop_id))).scalar_one_or_none()
    for uid in filter(None, [dispute.buyer_id, shop.owner_id if shop else None]):
        await notify(
            db, uid, NotificationType.system, title="Спор завершён",
            body=f"Решение по спору #{dispute.id}: {outcome_text}.",
            link="/disputes",
        )
    await db.flush()


async def load_detail(db: AsyncSession, dispute_id: int) -> Optional[Dispute]:
    return (await db.execute(
        select(Dispute)
        .options(
            selectinload(Dispute.messages),
            selectinload(Dispute.buyer),
            selectinload(Dispute.mediator),
        )
        .where(Dispute.id == dispute_id)
    )).scalar_one_or_none()

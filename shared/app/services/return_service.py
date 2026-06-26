"""
Return (RMA) service. Handles refunding a buyer for a returned order item and
reversing the corresponding seller payout when applicable.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    BalanceTransaction, BalanceTransactionType, NotificationType, OrderItem,
    ReturnRequest, ReturnRequestStatus, Transaction, TransactionType, User,
)
from app.services.notification_service import notify


async def refund_return(return_req: ReturnRequest, db: AsyncSession) -> Decimal:
    """
    Execute the monetary refund for an approved return. Credits the buyer's
    bonus/refund to their balance and reverses the seller's net for the
    returned quantity. Idempotent via the return's status (only runs once).
    Returns the refunded amount.
    """
    if return_req.status == ReturnRequestStatus.refunded:
        return Decimal("0")

    item = (await db.execute(
        select(OrderItem).where(OrderItem.id == return_req.order_item_id)
    )).scalar_one_or_none()
    if not item:
        return Decimal("0")

    # Refund amount: explicit amount if set, else pro-rated by quantity
    if return_req.refund_amount and return_req.refund_amount > 0:
        refund = return_req.refund_amount
    else:
        unit = item.price_at_time
        refund = (unit * return_req.quantity).quantize(Decimal("0.01"))
        return_req.refund_amount = refund

    # Credit the buyer (refund to their money balance)
    buyer = (await db.execute(select(User).where(User.id == return_req.buyer_id))).scalar_one_or_none()
    if buyer:
        buyer.balance += refund
        db.add(Transaction(
            user_id=buyer.id, type=TransactionType.order_refund, amount=refund,
            description=f"Возврат по заявке #{return_req.id}", balance_after=buyer.balance,
        ))
        db.add(BalanceTransaction(
            user_id=buyer.id, change=refund, type=BalanceTransactionType.credit,
            reference_type="return", reference_id=return_req.id,
            description=f"Возврат средств по заявке #{return_req.id}", balance_after=buyer.balance,
        ))

    # Reverse the seller's net for the returned quantity (if already paid out)
    if item.payout_status == "paid":
        seller_shop_owner = None
        from app.models.models import Shop
        shop = (await db.execute(select(Shop).where(Shop.id == item.shop_id))).scalar_one_or_none()
        if shop:
            seller = (await db.execute(select(User).where(User.id == shop.owner_id))).scalar_one_or_none()
            if seller and item.quantity > 0:
                per_unit_net = item.seller_net / item.quantity
                reverse = (per_unit_net * return_req.quantity).quantize(Decimal("0.01"))
                seller.balance -= reverse
                db.add(BalanceTransaction(
                    user_id=seller.id, change=-reverse, type=BalanceTransactionType.debit,
                    reference_type="return_reversal", reference_id=return_req.id,
                    description=f"Реверс выплаты по возврату #{return_req.id}",
                    balance_after=seller.balance,
                ))

    return_req.status = ReturnRequestStatus.refunded
    return_req.processed_at = datetime.now(timezone.utc)
    item.payout_status = "refunded"

    # 54-ФЗ: record a pending refund receipt (возврат прихода) for the returned
    # quantity. Guarded so a fiscalization hiccup never blocks the money refund.
    try:
        from app.core.config import settings as _settings
        if _settings.FISCAL_ENABLED and refund > 0:
            from app.models.models import FiscalReceiptType, Order, Payment, Product
            from app.services import fiscal_service
            product = (await db.execute(
                select(Product).where(Product.id == item.product_id)
            )).scalar_one_or_none()
            payment = (await db.execute(
                select(Payment).where(Payment.order_id == item.order_id)
            )).scalar_one_or_none()
            order = (await db.execute(
                select(Order).where(Order.id == item.order_id)
            )).scalar_one_or_none()
            if product is not None and order is not None:
                unit_price = (refund / return_req.quantity).quantize(Decimal("0.01")) \
                    if return_req.quantity else refund
                line_items, tax_system = await fiscal_service.build_income_line_items(
                    db, [{"title": product.title, "quantity": return_req.quantity,
                          "unit_price": unit_price, "shop_id": item.shop_id}]
                )
                contact = fiscal_service.customer_contact(buyer) if buyer else ""
                receipt = fiscal_service.build_receipt(contact, line_items, tax_system_code=tax_system)
                await fiscal_service.create_pending_receipt(
                    db, order, FiscalReceiptType.income_refund, contact, refund,
                    receipt, tax_system, payment_id=payment.id if payment else None,
                )
    except Exception:
        pass

    await notify(
        db, return_req.buyer_id, NotificationType.order_status,
        title="Возврат оформлен",
        body=f"Средства {refund} ₽ возвращены на ваш баланс",
        link="/orders",
    )
    return refund

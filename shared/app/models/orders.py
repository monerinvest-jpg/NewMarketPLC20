"""
Orders & money: cart, orders, payments, fiscal receipts, returns, disputes, custom orders.

Split out of the former monolithic models.py; import via app.models.models
(the re-export hub) or directly from this module.
"""
from app.models._base import *  # noqa: F401,F403 — shared imports/Enum/utcnow
from app.models._base import Enum, utcnow  # noqa: F401 — explicit for linters
from app.models.platform import CurrencyCode  # noqa: E501


class OrderStatus(str, enum.Enum):
    pending_payment = "pending_payment"
    paid = "paid"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    completed = "completed"
    cancelled = "cancelled"
    refunded = "refunded"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    cancelled = "cancelled"
    refunded = "refunded"


class PaymentGateway(str, enum.Enum):
    yookassa = "yookassa"
    cloudpayments = "cloudpayments"
    split = "split"            # BNPL / installments (pay in parts)


class FiscalReceiptType(str, enum.Enum):
    """54-ФЗ receipt type. income — приход (при оплате), income_refund —
    возврат прихода (при возврате средств покупателю)."""
    income = "income"
    income_refund = "income_refund"


class FiscalReceiptStatus(str, enum.Enum):
    """Lifecycle of a fiscal receipt registration in the ОФД (via YooKassa).
    pending  — sent to the gateway, waiting for ОФД registration;
    succeeded — registered (fiscal data received);
    canceled — gateway/ОФД declined the registration;
    failed   — local error before/while sending to the gateway."""
    pending = "pending"
    succeeded = "succeeded"
    canceled = "canceled"
    failed = "failed"


class TransactionType(str, enum.Enum):
    order_payment = "order_payment"
    order_refund = "order_refund"
    commission = "commission"
    payout = "payout"
    referral_reward = "referral_reward"
    bonus_used = "bonus_used"


class SubOrderStatus(str, enum.Enum):
    """Per-seller fulfillment status within a multi-shop order."""
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    completed = "completed"
    cancelled = "cancelled"


class ReturnRequestStatus(str, enum.Enum):
    requested = "requested"       # buyer opened a return
    approved = "approved"         # seller/admin accepted
    rejected = "rejected"         # declined
    in_transit = "in_transit"     # buyer shipped the item back
    refunded = "refunded"         # money returned to buyer


class DisputeStatus(str, enum.Enum):
    open = "open"                  # buyer↔seller discussion
    in_mediation = "in_mediation"  # escalated to a platform mediator
    resolved = "resolved"          # closed with an outcome
    cancelled = "cancelled"        # withdrawn by the buyer


class DisputeResolution(str, enum.Enum):
    none = "none"
    buyer_favor = "buyer_favor"    # refund to buyer
    seller_favor = "seller_favor"  # no refund
    partial = "partial"            # partial refund


class InstallmentPlan(Base):
    """A BNPL / pay-in-parts plan for an order. The provider settles the
    marketplace upfront; the buyer repays the provider per the schedule."""
    __tablename__ = "installment_plan"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("order.id"), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="split", nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    parts: Mapped[int] = mapped_column(Integer, nullable=False)
    part_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    schedule: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of {due_date, amount}
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# ─── Seller Academy (platform-authored education for sellers; reuses the LMS
#     pattern of courses → lessons → progress, decoupled from sellable products) ──


class CustomRequestStatus(str, enum.Enum):
    new = "new"                  # submitted, awaiting seller
    quoted = "quoted"            # seller sent an offer
    accepted = "accepted"        # buyer accepted the offer (agreement reached)
    in_production = "in_production"
    ready = "ready"              # finished, awaiting shipment/handover
    completed = "completed"
    declined = "declined"        # seller declined
    cancelled = "cancelled"      # buyer cancelled


class CustomRequest(Base):
    """A buyer's made-to-order request to a shop, negotiated to a seller offer
    (price / lead time / deposit) and tracked through production to completion."""
    __tablename__ = "custom_request"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    buyer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attachments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of image URLs
    status: Mapped[CustomRequestStatus] = mapped_column(
        Enum(CustomRequestStatus), default=CustomRequestStatus.new, nullable=False)
    # Current seller offer
    quoted_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    quoted_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deposit_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    offer_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    messages: Mapped[List["CustomMessage"]] = relationship(
        "CustomMessage", back_populates="request", cascade="all, delete-orphan", order_by="CustomMessage.created_at"
    )

    __table_args__ = (
        Index("ix_custom_request_buyer", "buyer_id"),
        Index("ix_custom_request_shop", "shop_id"),
    )


class CustomMessage(Base):
    __tablename__ = "custom_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("custom_request.id"), nullable=False)
    sender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of URLs
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    request: Mapped["CustomRequest"] = relationship("CustomRequest", back_populates="messages")


class CartItem(Base):
    __tablename__ = "cart_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    # Optional: set when the product has variants
    variant_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("product_variant.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="cart_items")
    product: Mapped["Product"] = relationship("Product", back_populates="cart_items")
    variant: Mapped[Optional["ProductVariant"]] = relationship("ProductVariant")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", "variant_id", name="uq_cart_user_product_variant"),
        Index("ix_cart_item_user_id", "user_id"),
    )


class Order(Base):
    __tablename__ = "order"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    buyer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    delivery_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    # Aggregate totals across all order items (for display only). The authoritative
    # per-seller financials — used for payouts — live on OrderItem.platform_fee /
    # OrderItem.seller_net, since a single order can contain products from multiple shops.
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    seller_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    commission_percent_used: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10.00"), nullable=False)
    bonus_used: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    promo_used: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    # Referral earnings spent on this order (covers up to 100% of the payable).
    referral_used: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False, server_default="0")
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.pending_payment, nullable=False)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False)
    coupon_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("coupon.id"), nullable=True)
    coupon_discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    # Gift options: gift wrapping (paid, gift_wrap_price) + a card message for the
    # recipient. The price (if wrapped) is added to the order total.
    is_gift: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    gift_wrap: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    gift_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Currency snapshot: prices are stored in base currency (RUB); these record
    # what the buyer actually saw/paid in, for display and receipts.
    currency: Mapped[CurrencyCode] = mapped_column(Enum(CurrencyCode), default=CurrencyCode.RUB, nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("1.000000"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    buyer: Mapped["User"] = relationship("User", back_populates="orders", foreign_keys=[buyer_id])
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    sub_orders: Mapped[List["SubOrder"]] = relationship("SubOrder", back_populates="order", cascade="all, delete-orphan")
    payment: Mapped[Optional["Payment"]] = relationship("Payment", back_populates="order", uselist=False)
    delivery_info: Mapped[Optional["DeliveryInfo"]] = relationship("DeliveryInfo", back_populates="order", uselist=False)
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="order")
    fiscal_receipts: Mapped[List["FiscalReceipt"]] = relationship(
        "FiscalReceipt", back_populates="order", cascade="all, delete-orphan"
    )
    coupon: Mapped[Optional["Coupon"]] = relationship("Coupon")

    __table_args__ = (
        Index("ix_order_buyer_id", "buyer_id"),
        Index("ix_order_status", "status"),
        Index("ix_order_created_at", "created_at"),
    )


class OrderItem(Base):
    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("order.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    variant_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("product_variant.id"), nullable=True)
    variant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # snapshot at purchase time
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    sub_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("sub_order.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_at_time: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Per-item financials: each shop in a multi-shop order has its own commission rate
    commission_percent_used: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="10.00")
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0.00")
    seller_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0.00")
    payout_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")  # pending|paid|refunded

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")
    shop: Mapped["Shop"] = relationship("Shop")
    sub_order: Mapped[Optional["SubOrder"]] = relationship("SubOrder", back_populates="items")

    __table_args__ = (
        Index("ix_order_item_order_id", "order_id"),
        Index("ix_order_item_shop_id", "shop_id"),
    )


class SubOrder(Base):
    """
    A per-seller slice of an order. A multi-shop order is split into one
    SubOrder per shop, each with its own fulfillment status and tracking number,
    so one seller shipping their items doesn't flip the whole order to "shipped".
    The order's overall status is derived from its sub-orders.
    """
    __tablename__ = "sub_order"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("order.id"), nullable=False)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    status: Mapped[SubOrderStatus] = mapped_column(Enum(SubOrderStatus), default=SubOrderStatus.processing, nullable=False)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    delivery_service: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Carrier's internal shipment id (e.g. CDEK order uuid), set when a shipment
    # is registered via API. Used to fetch the carrier's printable label later.
    carrier_uuid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="sub_orders")
    shop: Mapped["Shop"] = relationship("Shop")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="sub_order")

    __table_args__ = (
        UniqueConstraint("order_id", "shop_id", name="uq_sub_order_order_shop"),
        Index("ix_sub_order_order_id", "order_id"),
        Index("ix_sub_order_shop_id", "shop_id"),
    )


class ReturnRequest(Base):
    """
    A buyer's request to return purchased items and get a refund (RMA flow).
    Scoped to a single order item; the seller or admin approves/rejects, the
    buyer ships back, and on 'refunded' the money is returned to the buyer.
    """
    __tablename__ = "return_request"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("order_item.id"), nullable=False)
    buyer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReturnRequestStatus] = mapped_column(Enum(ReturnRequestStatus), default=ReturnRequestStatus.requested, nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    resolution_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    order_item: Mapped["OrderItem"] = relationship("OrderItem")
    buyer: Mapped["User"] = relationship("User", foreign_keys=[buyer_id])
    shop: Mapped["Shop"] = relationship("Shop")
    processed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[processed_by_id])

    __table_args__ = (
        Index("ix_return_request_buyer_id", "buyer_id"),
        Index("ix_return_request_shop_id", "shop_id"),
        Index("ix_return_request_status", "status"),
    )


class Payment(Base):
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("order.id"), nullable=False, unique=True)
    gateway: Mapped[PaymentGateway] = mapped_column(Enum(PaymentGateway), nullable=False)
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    confirmation_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="payment")
    fiscal_receipts: Mapped[List["FiscalReceipt"]] = relationship(
        "FiscalReceipt", back_populates="payment", cascade="all, delete-orphan"
    )


class FiscalReceipt(Base):
    """
    A 54-ФЗ fiscal receipt registered through YooKassa's built-in fiscalization.

    The receipt object is embedded in the YooKassa payment (income) or refund
    (income_refund) request; YooKassa forwards it to the ОФД and reports the
    registration outcome back via webhook. We snapshot what was sent (items,
    customer contact, totals) and track the registration status so the receipt
    can be shown to the buyer, audited by admins, and retried on failure.
    """
    __tablename__ = "fiscal_receipt"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("order.id"), nullable=False, index=True)
    payment_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("payment.id"), nullable=True)
    type: Mapped[FiscalReceiptType] = mapped_column(Enum(FiscalReceiptType), nullable=False)
    status: Mapped[FiscalReceiptStatus] = mapped_column(
        Enum(FiscalReceiptStatus), default=FiscalReceiptStatus.pending, nullable=False, index=True
    )
    # Snapshot of what was sent to the ОФД (so the receipt is reproducible even
    # if products/prices change later).
    customer_contact: Mapped[str] = mapped_column(String(255), nullable=False)  # email или телефон
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_system_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    items_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: список позиций чека
    # Fiscal data returned by the ОФД once registered.
    fiscal_document_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # ФД
    fiscal_storage_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)   # ФН
    fiscal_attribute: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)         # ФПД/ФП
    registered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="fiscal_receipts")
    payment: Mapped[Optional["Payment"]] = relationship("Payment", back_populates="fiscal_receipts")

    @property
    def items(self) -> list:
        """Receipt line items, decoded from the stored snapshot (for serialization)."""
        import json as _json
        try:
            return _json.loads(self.items_json) if self.items_json else []
        except Exception:
            return []

    # NB: no explicit Index() entries here — order_id/status already carry
    # column-level index=True; duplicating them broke metadata.create_all.


class Transaction(Base):
    """Financial transaction record."""
    __tablename__ = "transaction"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("order.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User")
    order: Mapped[Optional["Order"]] = relationship("Order", back_populates="transactions")

    __table_args__ = (
        Index("ix_transaction_user_id", "user_id"),
        Index("ix_transaction_type", "type"),
    )


class DeliveryInfo(Base):
    __tablename__ = "delivery_info"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("order.id"), nullable=False, unique=True)
    delivery_service: Mapped[str] = mapped_column(String(50), default="cdek", nullable=False)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    estimated_days: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    city_from: Mapped[str] = mapped_column(String(255), nullable=False, default="Москва")
    city_to: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="delivery_info")


class Dispute(Base):
    """
    A mediated conflict over an order. Opened by a buyer (or seller), discussed
    between the parties, and — if unresolved — escalated to a platform mediator
    (support/moderator) who decides the outcome and any refund.
    """
    __tablename__ = "dispute"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("order.id"), nullable=False, index=True)
    order_item_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("order_item.id"), nullable=True)
    buyer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False, index=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False, index=True)
    opened_by: Mapped[str] = mapped_column(String(10), default="buyer", nullable=False)  # buyer|seller
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DisputeStatus] = mapped_column(
        Enum(DisputeStatus), default=DisputeStatus.open, nullable=False, index=True
    )
    resolution: Mapped[DisputeResolution] = mapped_column(
        Enum(DisputeResolution), default=DisputeResolution.none, nullable=False
    )
    refund_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mediator_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    buyer: Mapped["User"] = relationship("User", foreign_keys=[buyer_id])
    mediator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[mediator_id])
    shop: Mapped["Shop"] = relationship("Shop")
    messages: Mapped[List["DisputeMessage"]] = relationship(
        "DisputeMessage", back_populates="dispute", cascade="all, delete-orphan",
        order_by="DisputeMessage.created_at",
    )


class DisputeMessage(Base):
    __tablename__ = "dispute_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dispute_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dispute.id"), nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    sender_role: Mapped[str] = mapped_column(String(10), nullable=False)  # buyer|seller|mediator|system
    text: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="messages")

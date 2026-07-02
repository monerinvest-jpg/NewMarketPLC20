"""
Platform: support, chat, notifications, promo/coupons, currencies, audit, settings, misc.

Split out of the former monolithic models.py; import via app.models.models
(the re-export hub) or directly from this module.
"""
from app.models._base import *  # noqa: F401,F403 — shared imports/Enum/utcnow
from app.models._base import Enum, utcnow  # noqa: F401 — explicit for linters


class ReportStatus(str, enum.Enum):
    open = "open"
    in_review = "in_review"
    resolved = "resolved"
    dismissed = "dismissed"


class DiscountType(str, enum.Enum):
    percent = "percent"
    fixed = "fixed"


class NotificationType(str, enum.Enum):
    order_status = "order_status"
    review_reply = "review_reply"
    review_moderated = "review_moderated"
    product_moderated = "product_moderated"
    question_answered = "question_answered"
    new_message = "new_message"
    payout = "payout"
    new_order = "new_order"
    shop_update = "shop_update"
    system = "system"


class SupportTicketStatus(str, enum.Enum):
    open = "open"                  # new, awaiting staff
    in_progress = "in_progress"    # a support agent is handling it
    pending_user = "pending_user"  # waiting on the user's reply
    resolved = "resolved"          # solved, may be reopened by the user
    closed = "closed"              # finalized


class SupportTicketPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class PromotionStatus(str, enum.Enum):
    pending = "pending"      # bid placed, awaiting auction settlement
    active = "active"        # currently displayed (auction winner or paid fixed feature)
    outbid = "outbid"        # lost the auction this round, not displayed/charged
    expired = "expired"      # period ended or funds ran out
    cancelled = "cancelled"  # cancelled by the seller


class PaidFeaturePricing(str, enum.Enum):
    fixed = "fixed"          # flat price for a period
    auction = "auction"      # price = bid; top N bids win the slots


class PromoType(str, enum.Enum):
    nplus = "nplus"      # buy X, get Y free (e.g. 2+1)
    volume = "volume"    # tiered discount by quantity (3+ → 10%, 5+ → 15%)


class CurrencyCode(str, enum.Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


# ─────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────


class Report(Base):
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'product', 'shop', 'user'
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.open, nullable=False)
    moderator_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    reporter: Mapped["User"] = relationship("User", back_populates="reports_filed", foreign_keys=[reporter_id])
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderator_id])

    __table_args__ = (
        Index("ix_report_status", "status"),
        Index("ix_report_target", "target_type", "target_id"),
    )


class Coupon(Base):
    __tablename__ = "coupon"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    discount_type: Mapped[DiscountType] = mapped_column(Enum(DiscountType), nullable=False)
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 = unlimited
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_order_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Notification(Base):
    """An in-app notification shown in the bell menu."""
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Optional deep-link the frontend can navigate to (e.g. "/orders/12")
    link: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_notification_user_id", "user_id"),
        Index("ix_notification_is_read", "is_read"),
    )


class ChatThread(Base):
    """
    A conversation between a buyer and a seller's shop. One thread per
    (buyer, shop) pair keeps all their messages together.
    """
    __tablename__ = "chat_thread"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    buyer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    buyer: Mapped["User"] = relationship("User")
    shop: Mapped["Shop"] = relationship("Shop")
    messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("buyer_id", "shop_id", name="uq_chat_buyer_shop"),
        Index("ix_chat_thread_buyer_id", "buyer_id"),
        Index("ix_chat_thread_shop_id", "shop_id"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_thread.id"), nullable=False)
    sender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    thread: Mapped["ChatThread"] = relationship("ChatThread", back_populates="messages")
    sender: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_chat_message_thread_id", "thread_id"),
    )


# ─── Block 3: Seller coupons & payout requests ──────────────────────────────────


class SellerCoupon(Base):
    """
    A discount coupon created by a seller, scoped to their own shop only.
    Distinct from the admin-managed global Coupon model.
    """
    __tablename__ = "seller_coupon"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    discount_type: Mapped[DiscountType] = mapped_column(Enum(DiscountType), default=DiscountType.percent, nullable=False)
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    min_order_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    usage_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    shop: Mapped["Shop"] = relationship("Shop")

    __table_args__ = (
        Index("ix_seller_coupon_shop_id", "shop_id"),
        Index("ix_seller_coupon_code", "code"),
    )


class HomepageBanner(Base):
    """A promotional banner shown on the homepage, managed from the admin panel."""
    __tablename__ = "homepage_banner"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CurrencyRate(Base):
    """
    Exchange rate from the base currency (RUB) to another currency. Admin-managed
    (or refreshed via a task). amount_in_currency = amount_in_rub * rate.
    """
    __tablename__ = "currency_rate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[CurrencyCode] = mapped_column(Enum(CurrencyCode), nullable=False, unique=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AuditLog(Base):
    """Append-only record of significant staff/system actions."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    actor: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_actor_id", "actor_id"),
        Index("ix_audit_log_created_at", "created_at"),
    )


class FeatureFlag(Base):
    """A named feature toggle with optional percentage rollout."""
    __tablename__ = "feature_flag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rollout_percent: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class SmsLog(Base):
    """
    Record of every SMS send attempt for statistics and troubleshooting.
    Stores the outcome (ok/failed), SMSC message id, cost, and any error.
    """
    __tablename__ = "sms_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)  # phone_verification|order_status|test|manual
    text_preview: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)   # sent|failed
    smsc_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    sms_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_sms_log_created_at", "created_at"),
        Index("ix_sms_log_purpose", "purpose"),
        Index("ix_sms_log_status", "status"),
    )


class Setting(Base):
    """
    Flexible key-value settings store.
    All platform-level configuration lives here so admins can edit it via the UI.
    """
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class SupportTicket(Base):
    """
    A user's support request. Conversation lives in SupportMessage. Tickets are
    triaged by support agents (UserRole.support), overseen by moderators, and
    fully editable by superadmins.
    """
    __tablename__ = "support_ticket"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)  # order|payment|account|product|other
    status: Mapped[SupportTicketStatus] = mapped_column(
        Enum(SupportTicketStatus), default=SupportTicketStatus.open, nullable=False, index=True
    )
    priority: Mapped[SupportTicketPriority] = mapped_column(
        Enum(SupportTicketPriority), default=SupportTicketPriority.normal, nullable=False
    )
    # The support agent currently handling the ticket (nullable until assigned).
    assigned_to_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True, index=True)
    # SLA escalation tracking: 0 = none, then bumped as the ticket ages without
    # a first response. Prevents repeated escalations on each SLA sweep.
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # First staff reply timestamp — used for response-time statistics.
    first_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    assigned_to: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_to_id])
    messages: Mapped[List["SupportMessage"]] = relationship(
        "SupportMessage", back_populates="ticket", cascade="all, delete-orphan",
        order_by="SupportMessage.created_at",
    )

    @property
    def is_overdue(self) -> bool:
        """True if the ticket is past its first-response SLA without a staff reply."""
        from app.core.config import settings
        if self.status in (SupportTicketStatus.resolved, SupportTicketStatus.closed):
            return False
        if self.first_response_at is not None:
            return False
        created = self.created_at
        if created is None:
            return False
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        threshold = datetime.now(timezone.utc) - timedelta(hours=settings.SUPPORT_SLA_FIRST_RESPONSE_HOURS)
        return created < threshold


class SupportMessage(Base):
    __tablename__ = "support_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("support_ticket.id"), nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    # Denormalized so we can render "support vs user" without loading the sender.
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    read_by_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_by_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    ticket: Mapped["SupportTicket"] = relationship("SupportTicket", back_populates="messages")
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])


class PaidFeature(Base):
    """
    Admin-managed catalog of monetizable features. Each row carries its price and
    an on/off switch, so the platform can enable/disable paid placements and set
    their cost from the admin panel without code changes.

    pricing_mode:
      - fixed:   flat `price` charged once per `billing_period`.
      - auction: `price` is the reserve (minimum daily bid); the top `slots`
                 bids win and are displayed.
    """
    __tablename__ = "paid_feature"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    placement: Mapped[str] = mapped_column(String(40), nullable=False)  # homepage|category|product_card|search
    pricing_mode: Mapped[PaidFeaturePricing] = mapped_column(
        Enum(PaidFeaturePricing), default=PaidFeaturePricing.fixed, nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    billing_period: Mapped[str] = mapped_column(String(10), default="day", nullable=False)  # day|week|once
    slots: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # auction winners shown
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Promotion(Base):
    """
    A seller's purchased placement or auction bid. For auction features
    (e.g. the homepage first row) `bid_amount` is the seller's daily bid; the
    settlement job ranks bids, marks the top `slots` as active (and charges
    them), and demotes the rest to `outbid`.
    """
    __tablename__ = "promotion"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False, index=True)
    product_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=True)
    feature_id: Mapped[int] = mapped_column(Integer, ForeignKey("paid_feature.id"), nullable=False)
    feature_key: Mapped[str] = mapped_column(String(64), nullable=False)
    placement: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    bid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[PromotionStatus] = mapped_column(
        Enum(PromotionStatus), default=PromotionStatus.pending, nullable=False, index=True
    )
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_charged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_spent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    # Ad analytics counters (for CTR / CPC / ROI).
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    shop: Mapped["Shop"] = relationship("Shop")
    product: Mapped[Optional["Product"]] = relationship("Product")
    feature: Mapped["PaidFeature"] = relationship("PaidFeature")


class PromotionStatDaily(Base):
    """
    Per-day ad counters for a promotion (impressions / clicks / spend), so the
    seller cabinet can chart campaign dynamics instead of lifetime totals only.
    Bumped by record_event (views/clicks) and by the auction settlement (spend).
    """
    __tablename__ = "promotion_stat_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    promotion_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("promotion.id"), nullable=False, index=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False, index=True)
    day: Mapped[datetime] = mapped_column(Date, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    __table_args__ = (
        UniqueConstraint("promotion_id", "day", name="uq_promo_stat_promo_day"),
    )


class AdWalletTransaction(Base):
    """
    Ledger for a shop's advertising wallet (Shop.ad_balance). Top-ups credit the
    wallet (optionally with a package bonus); promotion charges debit it. Kept
    separate from the payout balance so ad spend and earnings never mix.
    """
    __tablename__ = "ad_wallet_transaction"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False, index=True)
    change: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # + credit, − debit
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # topup|bonus|spend|refund
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    shop: Mapped["Shop"] = relationship("Shop")


class PromoRule(Base):
    """
    Seller-defined automatic promotion applied at the cart (no coupon code):
    - nplus:  buy `buy_quantity`, get `free_quantity` cheapest free;
    - volume: tiered percentage discount by line quantity (tiers_json).
    Scope: a product, a category, or the whole shop (both targets null).
    """
    __tablename__ = "promo_rule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    type: Mapped[PromoType] = mapped_column(Enum(PromoType), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Scope (both null → whole shop)
    product_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("category.id"), nullable=True)
    # nplus params
    buy_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    free_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # volume params: JSON list of {"min_qty": int, "percent": number}
    tiers_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    @property
    def tiers(self) -> list:
        import json as _json
        try:
            return _json.loads(self.tiers_json) if self.tiers_json else []
        except Exception:
            return []


class Bundle(Base):
    """A "комплект": a fixed set of products sold together at `bundle_price`.
    The saving is applied automatically when all bundle items are in the cart."""
    __tablename__ = "bundle"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bundle_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    items: Mapped[List["BundleItem"]] = relationship(
        "BundleItem", back_populates="bundle", cascade="all, delete-orphan"
    )


class BundleItem(Base):
    __tablename__ = "bundle_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bundle_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bundle.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    bundle: Mapped["Bundle"] = relationship("Bundle", back_populates="items")
    product: Mapped["Product"] = relationship("Product")


class GiftCertificateStatus(str, enum.Enum):
    active = "active"
    redeemed = "redeemed"
    cancelled = "cancelled"
    expired = "expired"


class GiftCertificate(Base):
    """A purchasable/issuable gift code worth a fixed amount. Redeeming it credits
    the redeemer's promo balance, which is spendable at checkout."""
    __tablename__ = "gift_certificate"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[GiftCertificateStatus] = mapped_column(
        Enum(GiftCertificateStatus), default=GiftCertificateStatus.active, nullable=False, index=True
    )
    purchaser_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    redeemed_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class PromoBalanceTransaction(Base):
    """Ledger for a user's promo balance (gift redemptions, checkout spend, adjustments)."""
    __tablename__ = "promo_balance_transaction"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False, index=True)
    change: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # + credit, − spend
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # gift_redeem|order_spend|adjust|refund
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class LoyaltyTier(Base):
    """
    Admin-configurable loyalty level. A buyer's tier is the highest active tier
    whose `min_spend` ≤ their qualifying spend. Each tier sets the cashback rate
    and perks. `retention_days` controls inactivity decay: if the buyer makes no
    qualifying purchase within that window, they drop one tier (0 = never).
    """
    __tablename__ = "loyalty_tier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # ordering: 1=lowest
    min_spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    cashback_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    free_shipping: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    perks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

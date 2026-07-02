"""
Shops & sellers: shop, staff, verification/requisites, plans, payouts, academy, campaigns.

Split out of the former monolithic models.py; import via app.models.models
(the re-export hub) or directly from this module.
"""
from app.models._base import *  # noqa: F401,F403 — shared imports/Enum/utcnow
from app.models._base import Enum, utcnow  # noqa: F401 — explicit for linters


class ShopStatus(str, enum.Enum):
    """Moderation lifecycle of a seller's shop."""
    pending = "pending"
    active = "active"
    rejected = "rejected"
    suspended = "suspended"


class TaxRegime(str, enum.Enum):
    """Seller's tax regime (RU). Determines which requisites are required."""
    self_employed = "self_employed"   # Самозанятость (НПД)
    individual = "individual"         # ИП — индивидуальный предприниматель
    company = "company"               # ООО — общество с ограниченной ответственностью


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    trial = "trial"
    expired = "expired"
    cancelled = "cancelled"


class PayoutRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    paid = "paid"


class PayoutSource(str, enum.Enum):
    """Which balance a payout request draws from."""
    sales = "sales"        # seller's sales earnings (User.balance)
    referral = "referral"  # referral earnings (User.referral_balance)


class Shop(Base):
    __tablename__ = "shop"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Storefront customization (shop page settings managed by the seller)
    banner_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    accent_color: Mapped[str] = mapped_column(String(9), default="#f97316", nullable=False)
    tagline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # NULL means use global commission. Resolution order is documented in
    # commission_service.get_effective_commission: admin override → plan → global.
    commission_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[ShopStatus] = mapped_column(Enum(ShopStatus), default=ShopStatus.pending, nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Trust signals. kyc_verified is set when document verification is approved;
    # vip_until is the paid-VIP expiry. The effective badge (verified/vip) also
    # factors in reputation thresholds — computed in trust_service.
    kyc_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    vip_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    business_hours: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.00"), nullable=False)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Separate wallet that funds paid promotion (kept apart from payout balance).
    ad_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_sales: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    owner: Mapped["User"] = relationship("User", back_populates="shop")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="shop")
    subscription: Mapped[Optional["SellerSubscription"]] = relationship(
        "SellerSubscription", back_populates="shop", uselist=False
    )

    __table_args__ = (
        Index("ix_shop_is_active", "is_active"),
        Index("ix_shop_status", "status"),
    )


class ShopMemberRole(str, enum.Enum):
    owner = "owner"      # the shop owner (implicit, all permissions)
    manager = "manager"  # full operational access (all permissions)
    staff = "staff"      # only the explicitly granted permissions


class ShopMember(Base):
    """A user attached to a shop as staff, with granular per-area permissions.
    The shop owner is implicit (Shop.owner_id) and always has everything."""
    __tablename__ = "shop_member"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    role: Mapped[ShopMemberRole] = mapped_column(Enum(ShopMemberRole), default=ShopMemberRole.staff, nullable=False)
    permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of permission keys
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("shop_id", "user_id", name="uq_shop_member_shop_user"),
    )


class SellerVerificationStatus(str, enum.Enum):
    none = "none"
    pending = "pending"
    verified = "verified"
    rejected = "rejected"


class SellerVerification(Base):
    """KYC document verification for a shop. Approval sets Shop.kyc_verified and
    grants the «Проверенный» badge. Documents are stored as private S3 keys."""
    __tablename__ = "seller_verification"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), unique=True, nullable=False)
    status: Mapped[SellerVerificationStatus] = mapped_column(
        Enum(SellerVerificationStatus), default=SellerVerificationStatus.pending, nullable=False)
    document_keys: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of private storage keys
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)            # applicant note
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)          # reviewer reason on reject
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CampaignChannel(str, enum.Enum):
    email = "email"
    inapp = "inapp"    # in-app notification (and push, if configured)


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    sending = "sending"
    sent = "sent"
    failed = "failed"


class Campaign(Base):
    """A marketing broadcast to a user segment over email or in-app notifications."""
    __tablename__ = "campaign"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[CampaignChannel] = mapped_column(Enum(CampaignChannel), default=CampaignChannel.email, nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    segment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON filter
    status: Mapped[CampaignStatus] = mapped_column(Enum(CampaignStatus), default=CampaignStatus.draft, nullable=False)
    recipients: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AcademyCourse(Base):
    __tablename__ = "academy_course"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    level: Mapped[str] = mapped_column(String(20), default="beginner", nullable=False)  # beginner|intermediate|advanced
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    lessons: Mapped[List["AcademyLesson"]] = relationship(
        "AcademyLesson", back_populates="course", cascade="all, delete-orphan", order_by="AcademyLesson.sort_order"
    )


class AcademyLesson(Base):
    __tablename__ = "academy_lesson"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("academy_course.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(10), default="text", nullable=False)  # text|video|link
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)        # markdown/text for text lessons
    video_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # video or external link
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    course: Mapped["AcademyCourse"] = relationship("AcademyCourse", back_populates="lessons")


class AcademyProgress(Base):
    __tablename__ = "academy_progress"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    lesson_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("academy_lesson.id"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_academy_progress_user_lesson"),
    )


# ─── Custom / made-to-order requests (Etsy-style commissions) ───────────────────


class ShopIntegration(Base):
    """
    A shop's connection to an external platform (VK for now): the OAuth token
    and the linked community, so the seller can (re-)import their catalog.
    One integration per (shop, provider).
    """
    __tablename__ = "shop_integration"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="vk")
    # OAuth access token of the SELLER (scope: market, groups, offline).
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    community_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    community_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("shop_id", "provider", name="uq_shop_integration_shop_provider"),
    )


class PayoutRequest(Base):
    """
    A seller's request to withdraw their accrued balance to an external
    account. Admin reviews and approves/rejects; on payout the amount is
    deducted from the seller's balance.
    """
    __tablename__ = "payout_request"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Which balance this withdrawal draws from (sales earnings vs referral earnings).
    source: Mapped[PayoutSource] = mapped_column(Enum(PayoutSource), default=PayoutSource.sales, nullable=False, server_default="sales")
    status: Mapped[PayoutRequestStatus] = mapped_column(Enum(PayoutRequestStatus), default=PayoutRequestStatus.pending, nullable=False)
    # Free-form payout destination (card number masked, bank account, etc.)
    payout_details: Mapped[str] = mapped_column(String(512), nullable=False)
    admin_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    processed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[processed_by_id])

    __table_args__ = (
        Index("ix_payout_request_user_id", "user_id"),
        Index("ix_payout_request_status", "status"),
    )


# ─── Block 5: Homepage banners ──────────────────────────────────────────────────


class ChatTemplate(Base):
    """A canned reply a seller can reuse in buyer chats."""
    __tablename__ = "chat_template"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    shop: Mapped["Shop"] = relationship("Shop")

    __table_args__ = (
        Index("ix_chat_template_shop_id", "shop_id"),
    )


class SellerRequisites(Base):
    """
    Legal/banking requisites for a seller, captured at registration. Which fields
    are required depends on tax_regime (self-employed needs the least; ООО needs
    КПП and ОГРН). Stored one-to-one with the shop.
    """
    __tablename__ = "seller_requisites"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), unique=True, nullable=False)
    tax_regime: Mapped[TaxRegime] = mapped_column(Enum(TaxRegime), nullable=False)
    # Common
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)  # ФИО или наименование
    inn: Mapped[str] = mapped_column(String(12), nullable=False)          # ИНН (10 для ООО, 12 для ИП/самозан.)
    # ИП / ООО
    ogrn: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)   # ОГРН/ОГРНИП
    kpp: Mapped[Optional[str]] = mapped_column(String(9), nullable=True)     # КПП (только ООО)
    legal_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Фискализация (54-ФЗ): ставка НДС и СНО продавца. Если не заданы — берутся
    # платформенные значения по умолчанию из настроек (FISCAL_VAT_CODE / FISCAL_TAX_SYSTEM_CODE).
    # vat_code: 1=без НДС, 2=0%, 3=10%, 4=20%, 5=10/110, 6=20/120 (коды ЮKassa).
    vat_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # tax_system_code: 1=ОСН, 2=УСН доход, 3=УСН доход-расход, 4=ЕНВД, 5=ЕСХН, 6=Патент.
    tax_system_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Banking (для выплат)
    bank_account: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)   # расчётный счёт
    bank_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bik: Mapped[Optional[str]] = mapped_column(String(9), nullable=True)
    corr_account: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    shop: Mapped["Shop"] = relationship("Shop")


class SellerPlan(Base):
    """
    A seller subscription tariff, fully managed from the admin panel.

    Each plan defines its own commission rate, so the platform can offer the
    classic trade-off: a free plan with a HIGHER commission, or a paid plan
    with a LOWER commission. The monthly price and an optional free-trial
    period (e.g. "first month free") are configurable.
    """
    __tablename__ = "seller_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Monthly price; 0 means a free plan
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    # The commission rate sellers on this plan pay. This is the plan's whole point.
    commission_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    # Free trial length in days (e.g. 30 = "first month free"). 0 = no trial.
    trial_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Marks the plan assigned to new sellers / used when paid placement is OFF
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    subscriptions: Mapped[List["SellerSubscription"]] = relationship("SellerSubscription", back_populates="plan")


class SellerSubscription(Base):
    """A seller's current subscription to a SellerPlan."""
    __tablename__ = "seller_subscription"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False, unique=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("seller_plan.id"), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.active, nullable=False
    )
    # When the current paid/trial period ends. NULL for free plans (never expires).
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    shop: Mapped["Shop"] = relationship("Shop", back_populates="subscription")
    plan: Mapped["SellerPlan"] = relationship("SellerPlan", back_populates="subscriptions")

    __table_args__ = (
        Index("ix_seller_subscription_shop_id", "shop_id"),
        Index("ix_seller_subscription_status", "status"),
    )


class ShopFollow(Base):
    """A buyer following a shop — drives the "shop updates" feed and notifications
    when the shop publishes new products or starts a flash sale."""
    __tablename__ = "shop_follow"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False, index=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "shop_id", name="uq_shop_follow"),
    )

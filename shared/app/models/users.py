"""
Users & identity: accounts, verification codes, addresses, referrals, balance.

Split out of the former monolithic models.py; import via app.models.models
(the re-export hub) or directly from this module.
"""
from app.models._base import *  # noqa: F401,F403 — shared imports/Enum/utcnow
from app.models._base import Enum, utcnow  # noqa: F401 — explicit for linters
from app.models.shops import TaxRegime  # noqa: E501


class UserRole(str, enum.Enum):
    buyer = "buyer"
    seller = "seller"
    support = "support"       # Поддержка пользователей (под руководством модератора)
    moderator = "moderator"
    superadmin = "superadmin"


class VerificationPurpose(str, enum.Enum):
    email = "email"
    phone = "phone"


class ReferralType(str, enum.Enum):
    buyer = "buyer"
    seller = "seller"


class BalanceTransactionType(str, enum.Enum):
    credit = "credit"
    debit = "debit"


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.buyer, nullable=False)
    referral_code: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True, index=True)
    # Monetary balance for sellers (real money); bonus balance for buyers (points)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    bonus_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    # Promo balance funded by gift certificates / promo campaigns (spendable at checkout).
    promo_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    # Referral earnings (real money): accrued lifelong from referred users' orders,
    # withdrawable to a bank account (with tax status) and spendable up to 100% at checkout.
    referral_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False, server_default="0")
    # Loyalty program state (tier by qualifying spend, with inactivity decay).
    loyalty_tier_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("loyalty_tier.id"), nullable=True)
    qualifying_spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    tier_since: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_qualifying_order_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Verification status. New users start with email_verified=False and confirm
    # via a code emailed to them. phone_verified is set after an SMS code is
    # confirmed (only when SMS is enabled in admin).
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Marketing consent: when True the user is excluded from email/push campaigns.
    marketing_opt_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    # Two-factor authentication (TOTP). Secret is set when 2FA is enabled.
    totp_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_backup_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of hashed codes
    # Notification channel preferences
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    referred_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    shop: Mapped[Optional["Shop"]] = relationship("Shop", back_populates="owner", uselist=False)
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="buyer", foreign_keys="Order.buyer_id")
    cart_items: Mapped[List["CartItem"]] = relationship("CartItem", back_populates="user")
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="user", foreign_keys="Review.user_id")
    favorites: Mapped[List["Favorite"]] = relationship("Favorite", back_populates="user")
    balance_transactions: Mapped[List["BalanceTransaction"]] = relationship("BalanceTransaction", back_populates="user")
    reports_filed: Mapped[List["Report"]] = relationship("Report", back_populates="reporter", foreign_keys="Report.reporter_id")

    __table_args__ = (
        Index("ix_user_role", "role"),
        Index("ix_user_is_active", "is_active"),
    )


class Referral(Base):
    __tablename__ = "referral"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    referred_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False, unique=True)
    type: Mapped[ReferralType] = mapped_column(Enum(ReferralType), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    reward_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    referrer: Mapped["User"] = relationship("User", foreign_keys=[referrer_id])
    referred_user: Mapped["User"] = relationship("User", foreign_keys=[referred_user_id])
    rewards: Mapped[List["ReferralReward"]] = relationship("ReferralReward", back_populates="referral")

    __table_args__ = (
        Index("ix_referral_referrer_id", "referrer_id"),
    )


class ReferralReward(Base):
    __tablename__ = "referral_reward"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    referral_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("referral.id"), nullable=False)
    # The order this reward was earned from. Lifelong referrals pay out on every
    # completed order, so (referral_id, order_id) is unique to prevent double-pay.
    order_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("order.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[ReferralType] = mapped_column(Enum(ReferralType), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    referral: Mapped["Referral"] = relationship("Referral", back_populates="rewards")

    __table_args__ = (
        UniqueConstraint("referral_id", "order_id", name="uq_referral_reward_referral_order"),
    )


class WithdrawalAccount(Base):
    """A user's bank/tax details for withdrawing referral earnings. Any user
    (not just sellers) can fill this; a valid tax_regime (self-employed/ИП/ООО)
    is required to request a referral payout."""
    __tablename__ = "withdrawal_account"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), unique=True, nullable=False)
    tax_regime: Mapped[TaxRegime] = mapped_column(Enum(TaxRegime), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)   # ФИО / наименование
    inn: Mapped[str] = mapped_column(String(12), nullable=False)
    account_details: Mapped[str] = mapped_column(String(512), nullable=False)  # счёт/карта/реквизиты
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class BalanceTransaction(Base):
    """Tracks all changes to user balances."""
    __tablename__ = "balance_transaction"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    change: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # positive = credit, negative = debit
    type: Mapped[BalanceTransactionType] = mapped_column(Enum(BalanceTransactionType), nullable=False)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'order', 'referral', etc.
    reference_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="balance_transactions")

    __table_args__ = (
        Index("ix_balance_tx_user_id", "user_id"),
    )


class Address(Base):
    """A saved delivery address in the buyer's address book."""
    __tablename__ = "address"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    street: Mapped[str] = mapped_column(String(255), nullable=False)
    building: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    apartment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_address_user_id", "user_id"),
    )


class VerificationCode(Base):
    """
    A short-lived numeric code for confirming an email address or phone number.
    A new request for the same (user, purpose) supersedes older unused codes.
    """
    __tablename__ = "verification_code"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    purpose: Mapped[VerificationPurpose] = mapped_column(Enum(VerificationPurpose), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)  # email or phone the code was sent to
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_verification_code_user_purpose", "user_id", "purpose"),
    )


class PasswordResetToken(Base):
    """
    One-time token for password recovery. A new request invalidates any
    previous unused token for the same user (only one active token at a time).
    """
    __tablename__ = "password_reset_token"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_password_reset_token_token", "token"),
        Index("ix_password_reset_token_user_id", "user_id"),
    )

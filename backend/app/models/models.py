"""
All SQLAlchemy ORM models for the marketplace.
"""
import enum
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class UserRole(str, enum.Enum):
    buyer = "buyer"
    seller = "seller"
    support = "support"       # Поддержка пользователей (под руководством модератора)
    moderator = "moderator"
    superadmin = "superadmin"


class ProductStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    rejected = "rejected"
    blocked = "blocked"


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


class VerificationPurpose(str, enum.Enum):
    email = "email"
    phone = "phone"


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


class ReferralType(str, enum.Enum):
    buyer = "buyer"
    seller = "seller"


class ReportStatus(str, enum.Enum):
    open = "open"
    in_review = "in_review"
    resolved = "resolved"
    dismissed = "dismissed"


class DiscountType(str, enum.Enum):
    percent = "percent"
    fixed = "fixed"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    trial = "trial"
    expired = "expired"
    cancelled = "cancelled"


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


class PayoutRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    paid = "paid"


class BalanceTransactionType(str, enum.Enum):
    credit = "credit"
    debit = "debit"


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


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("category.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    image: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    parent: Mapped[Optional["Category"]] = relationship("Category", remote_side="Category.id", back_populates="children")
    children: Mapped[List["Category"]] = relationship("Category", back_populates="parent")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("category.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    # SEO-friendly slug, e.g. "krasnaya-futbolka-123". Nullable for legacy rows.
    slug: Mapped[Optional[str]] = mapped_column(String(600), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    compare_at_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weight_g: Mapped[int] = mapped_column(Integer, default=500, nullable=False)  # weight in grams for shipping
    status: Mapped[ProductStatus] = mapped_column(Enum(ProductStatus), default=ProductStatus.pending, nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.00"), nullable=False)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    views_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    shop: Mapped["Shop"] = relationship("Shop", back_populates="products")
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    images: Mapped[List["ProductImage"]] = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    cart_items: Mapped[List["CartItem"]] = relationship("CartItem", back_populates="product")
    order_items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="product")
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="product")
    favorites: Mapped[List["Favorite"]] = relationship("Favorite", back_populates="product")
    variants: Mapped[List["ProductVariant"]] = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    attribute_values: Mapped[List["ProductAttributeValue"]] = relationship("ProductAttributeValue", back_populates="product", cascade="all, delete-orphan")
    questions: Mapped[List["ProductQuestion"]] = relationship("ProductQuestion", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_product_shop_id", "shop_id"),
        Index("ix_product_category_id", "category_id"),
        Index("ix_product_status", "status"),
        Index("ix_product_price", "price"),
        Index("ix_product_rating", "rating"),
        Index("ix_product_title", "title"),
    )


class ProductCoPurchase(Base):
    """
    Materialized "bought together" signal: how often `related_product_id` appears
    in the same real (paid+) order as `product_id`. Directed pairs are stored
    both ways so a recommendation lookup is a single indexed read ordered by
    score. Rebuilt periodically by recommendation_service.rebuild_co_purchase.
    """
    __tablename__ = "product_co_purchase"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    related_product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("product_id", "related_product_id", name="uq_co_purchase_pair"),
        Index("ix_co_purchase_lookup", "product_id", "score"),
    )


class ProductImage(Base):
    __tablename__ = "product_image"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="images")

    __table_args__ = (
        Index("ix_product_image_product_id", "product_id"),
    )


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
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.pending_payment, nullable=False)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False)
    coupon_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("coupon.id"), nullable=True)
    coupon_discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
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

    __table_args__ = (
        Index("ix_fiscal_receipt_order_id", "order_id"),
        Index("ix_fiscal_receipt_status", "status"),
    )


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
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[ReferralType] = mapped_column(Enum(ReferralType), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    referral: Mapped["Referral"] = relationship("Referral", back_populates="rewards")


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


class Review(Base):
    __tablename__ = "review"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–5
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.pending, nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    moderated_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Verified-purchase provenance: the order this review is backed by, and a
    # denormalized flag for fast filtering/badging.
    is_verified_purchase: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("order.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="reviews", foreign_keys=[user_id])
    product: Mapped["Product"] = relationship("Product", back_populates="reviews")
    moderated_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by_id])
    reply: Mapped[Optional["ReviewReply"]] = relationship("ReviewReply", back_populates="review", uselist=False, cascade="all, delete-orphan")
    votes: Mapped[List["ReviewVote"]] = relationship("ReviewVote", back_populates="review", cascade="all, delete-orphan")
    photos: Mapped[List["ReviewPhoto"]] = relationship("ReviewPhoto", back_populates="review", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_review_user_product"),
        Index("ix_review_product_id", "product_id"),
        Index("ix_review_status", "status"),
    )


class ReviewReply(Base):
    """A seller's single reply to a customer review."""
    __tablename__ = "review_reply"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("review.id"), nullable=False, unique=True)
    seller_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    review: Mapped["Review"] = relationship("Review", back_populates="reply")
    seller: Mapped["User"] = relationship("User")


class ReviewVote(Base):
    """Tracks which users marked a review as helpful ('like')."""
    __tablename__ = "review_vote"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("review.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    review: Mapped["Review"] = relationship("Review", back_populates="votes")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("review_id", "user_id", name="uq_review_vote_user"),
        Index("ix_review_vote_review_id", "review_id"),
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


class Favorite(Base):
    __tablename__ = "favorite"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="favorites")
    product: Mapped["Product"] = relationship("Product", back_populates="favorites")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_favorite_user_product"),
        Index("ix_favorite_user_id", "user_id"),
    )


# ─── Block 1: Product variants, attributes, questions, review photos ────────────

class ProductVariant(Base):
    """
    A specific purchasable variation of a product (e.g. size M / color red),
    each with its own SKU, price override and independent stock. When a product
    has variants, the cart/order references a variant; products without variants
    behave exactly as before (single implicit variant = the product itself).
    """
    __tablename__ = "product_variant"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Human-readable variant name, e.g. "Размер M / Красный"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Optional price override; NULL means use the product's base price
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")

    __table_args__ = (
        Index("ix_product_variant_product_id", "product_id"),
    )


class Attribute(Base):
    """
    A filterable product attribute definition, e.g. "Бренд", "Материал".
    Managed by admins; products attach values via ProductAttributeValue.
    """
    __tablename__ = "attribute"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # If True, shown as a filter facet in the catalog
    is_filterable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    values: Mapped[List["ProductAttributeValue"]] = relationship("ProductAttributeValue", back_populates="attribute", cascade="all, delete-orphan")


class ProductAttributeValue(Base):
    """A concrete attribute value for a product, e.g. (Бренд = Nike)."""
    __tablename__ = "product_attribute_value"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    attribute_id: Mapped[int] = mapped_column(Integer, ForeignKey("attribute.id"), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="attribute_values")
    attribute: Mapped["Attribute"] = relationship("Attribute", back_populates="values")

    __table_args__ = (
        Index("ix_product_attr_value_product_id", "product_id"),
        Index("ix_product_attr_value_attribute_id", "attribute_id"),
        Index("ix_product_attr_value_value", "value"),
    )


class ProductQuestion(Base):
    """
    A buyer's question about a product, optionally answered by the seller.
    Public Q&A visible on the product page.
    """
    __tablename__ = "product_question"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answered_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="questions")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    answered_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[answered_by_id])

    __table_args__ = (
        Index("ix_product_question_product_id", "product_id"),
    )


class ReviewPhoto(Base):
    """A photo attached to a product review."""
    __tablename__ = "review_photo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("review.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    review: Mapped["Review"] = relationship("Review", back_populates="photos")

    __table_args__ = (
        Index("ix_review_photo_review_id", "review_id"),
    )


# ─── Block 2: Notifications & buyer-seller chat ─────────────────────────────────

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


class ProductSubscription(Base):
    """
    A buyer's subscription to be notified about a product: either when it comes
    back in stock or when its price drops below a target. Powers "notify me"
    on out-of-stock items and price-drop alerts.
    """
    __tablename__ = "product_subscription"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    # 'back_in_stock' or 'price_drop'
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # For price_drop: notify when price <= target_price
    target_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    is_notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User")
    product: Mapped["Product"] = relationship("Product")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", "kind", name="uq_product_sub_user_product_kind"),
        Index("ix_product_subscription_product_id", "product_id"),
    )


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


class WishlistCollection(Base):
    """A named wishlist/collection, e.g. 'На день рождения'."""
    __tablename__ = "wishlist_collection"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User")
    items: Mapped[List["WishlistItem"]] = relationship(
        "WishlistItem", back_populates="collection", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_wishlist_collection_user_id", "user_id"),
    )


class WishlistItem(Base):
    __tablename__ = "wishlist_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("wishlist_collection.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    collection: Mapped["WishlistCollection"] = relationship("WishlistCollection", back_populates="items")
    product: Mapped["Product"] = relationship("Product")

    __table_args__ = (
        UniqueConstraint("collection_id", "product_id", name="uq_wishlist_collection_product"),
        Index("ix_wishlist_item_collection_id", "collection_id"),
    )


class ProductView(Base):
    """A record that a user viewed a product, powering 'recently viewed'."""
    __tablename__ = "product_view"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    product: Mapped["Product"] = relationship("Product")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_product_view_user_product"),
        Index("ix_product_view_user_id", "user_id"),
    )


class StockMovement(Base):
    """An auditable change to a product's/variant's stock level."""
    __tablename__ = "stock_movement"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    variant_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("product_variant.id"), nullable=True)
    change: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    product: Mapped["Product"] = relationship("Product")

    __table_args__ = (
        Index("ix_stock_movement_product_id", "product_id"),
    )


class FlashSale(Base):
    """A time-boxed discount on a product, set by the seller."""
    __tablename__ = "flash_sale"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    product: Mapped["Product"] = relationship("Product")
    shop: Mapped["Shop"] = relationship("Shop")

    __table_args__ = (
        Index("ix_flash_sale_product_id", "product_id"),
        Index("ix_flash_sale_shop_id", "shop_id"),
        Index("ix_flash_sale_active_window", "is_active", "starts_at", "ends_at"),
    )


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

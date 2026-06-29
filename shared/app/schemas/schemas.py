"""
Pydantic v2 schemas for request/response validation.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.models import (
    BalanceTransactionType, DiscountType, FiscalReceiptStatus, FiscalReceiptType,
    OrderStatus, PaymentGateway,
    PaymentStatus, ProductStatus, ProductType, CategoryKind, LessonType, ReferralType, ReportStatus,
    TransactionType, UserRole, ReviewStatus,
)


# ─────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────

class OrmBase(BaseModel):
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


# ─────────────────────────────────────────────
# User
# ─────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=2)
    phone: Optional[str] = None
    role: UserRole = UserRole.buyer
    referral_code: Optional[str] = None  # code of the referrer


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)


class UserAdminUpdate(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    is_staff: Optional[bool] = None


class UserOut(OrmBase):
    id: int
    email: str
    full_name: str
    phone: Optional[str]
    role: UserRole
    referral_code: Optional[str]
    balance: Decimal
    bonus_balance: Decimal
    is_active: bool
    is_staff: bool
    is_superuser: bool
    email_verified: bool = False
    phone_verified: bool = False
    created_at: datetime


class UserProfile(OrmBase):
    id: int
    email: str
    full_name: str
    phone: Optional[str]
    role: UserRole
    referral_code: Optional[str]
    balance: Decimal
    bonus_balance: Decimal
    created_at: datetime


# ─────────────────────────────────────────────
# Shop
# ─────────────────────────────────────────────

class ShopCreate(BaseModel):
    name: str = Field(min_length=2)
    description: Optional[str] = None


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    accent_color: Optional[str] = Field(None, max_length=9)
    tagline: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class ShopAdminUpdate(BaseModel):
    is_active: Optional[bool] = None
    commission_percent: Optional[Decimal] = Field(None, ge=0, le=100)


class ShopOut(OrmBase):
    id: int
    owner_id: int
    name: str
    description: Optional[str]
    logo_url: Optional[str]
    banner_url: Optional[str]
    accent_color: str
    tagline: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    commission_percent: Optional[Decimal]
    is_active: bool
    status: str = "active"
    moderation_reason: Optional[str] = None
    business_hours: Optional[str] = None
    rating: Decimal
    reviews_count: int = 0
    total_sales: int
    created_at: datetime


# ─────────────────────────────────────────────
# Category
# ─────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    slug: Optional[str] = None  # auto-generated from name if omitted
    parent_id: Optional[int] = None
    image: Optional[str] = None
    sort_order: int = 0
    kind: Optional[CategoryKind] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    parent_id: Optional[int] = None
    image: Optional[str] = None
    sort_order: Optional[int] = None
    kind: Optional[CategoryKind] = None


class CategoryOut(OrmBase):
    id: int
    parent_id: Optional[int]
    name: str
    slug: str
    image: Optional[str]
    sort_order: int
    kind: Optional[CategoryKind] = None
    children: List["CategoryOut"] = []


CategoryOut.model_rebuild()


# ─────────────────────────────────────────────
# Product
# ─────────────────────────────────────────────

class ProductImageOut(OrmBase):
    id: int
    url: str
    is_main: bool
    sort_order: int


class ProductCreate(BaseModel):
    category_id: int
    title: str = Field(min_length=3)
    description: Optional[str] = None
    price: Decimal = Field(gt=0)
    compare_at_price: Optional[Decimal] = None
    # Ignored for digital/course products (unlimited stock); defaults to 0.
    quantity: int = Field(default=0, ge=0)
    weight_g: int = Field(default=500, ge=1)
    product_type: ProductType = ProductType.physical


class ProductUpdate(BaseModel):
    category_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0)
    compare_at_price: Optional[Decimal] = None
    quantity: Optional[int] = Field(None, ge=0)
    weight_g: Optional[int] = None
    product_type: Optional[ProductType] = None


class ProductModerationUpdate(BaseModel):
    status: ProductStatus
    moderation_reason: Optional[str] = None


class ProductOut(OrmBase):
    id: int
    shop_id: int
    category_id: int
    title: str
    slug: Optional[str] = None
    description: Optional[str]
    price: Decimal
    compare_at_price: Optional[Decimal]
    quantity: int
    weight_g: int
    product_type: ProductType = ProductType.physical
    status: ProductStatus
    moderation_reason: Optional[str]
    rating: Decimal
    reviews_count: int
    views_count: int
    images: List[ProductImageOut] = []
    created_at: datetime
    # Populated when a flash sale is currently running on this product
    flash_price: Optional[Decimal] = None
    flash_discount_percent: Optional[Decimal] = None
    flash_ends_at: Optional[datetime] = None


# ─────────────────────────────────────────────
# Digital goods (files, entitlements)
# ─────────────────────────────────────────────

class DigitalAssetOut(OrmBase):
    """A digital file of a product. NEVER exposes storage_key (internal)."""
    id: int
    file_name: str
    content_type: str
    size_bytes: int
    sort_order: int


class EntitlementFileOut(BaseModel):
    asset_id: int
    file_name: str
    content_type: str
    size_bytes: int


class EntitlementOut(BaseModel):
    """A buyer's purchased digital product, shown in their "Обучение"/downloads."""
    id: int
    product_id: int
    product_title: str
    product_slug: Optional[str] = None
    order_id: int
    granted_at: datetime
    revoked: bool
    download_count: int
    files: List[EntitlementFileOut] = []


# ─────────────────────────────────────────────
# Courses / LMS
# ─────────────────────────────────────────────

class CourseUpsert(BaseModel):
    level: Optional[str] = None
    language: Optional[str] = None


class ModuleCreate(BaseModel):
    title: str = Field(min_length=1)
    sort_order: int = 0


class ModuleUpdate(BaseModel):
    title: Optional[str] = None
    sort_order: Optional[int] = None


class LessonCreate(BaseModel):
    title: str = Field(min_length=1)
    lesson_type: LessonType
    text_body: Optional[str] = None       # for text lessons
    is_preview: bool = False
    sort_order: int = 0
    duration_seconds: int = 0


class LessonUpdate(BaseModel):
    title: Optional[str] = None
    text_body: Optional[str] = None
    is_preview: Optional[bool] = None
    sort_order: Optional[int] = None
    duration_seconds: Optional[int] = None


class LessonOut(BaseModel):
    id: int
    title: str
    lesson_type: LessonType
    duration_seconds: int
    is_preview: bool
    sort_order: int
    has_file: bool = False
    locked: bool = True          # true unless the requester is entitled or it's a preview
    completed: bool = False
    text_body: Optional[str] = None   # included only when unlocked and type=text


class ModuleOut(BaseModel):
    id: int
    title: str
    sort_order: int
    lessons: List[LessonOut] = []


class CourseOut(BaseModel):
    id: int
    product_id: int
    shop_id: int
    title: str
    slug: Optional[str] = None
    level: Optional[str] = None
    language: Optional[str] = None
    has_intro_video: bool = False
    enrolled: bool = False
    total_lessons: int = 0
    completed_lessons: int = 0
    progress_percent: int = 0
    modules: List[ModuleOut] = []


class ProductListOut(OrmBase):
    id: int
    shop_id: int
    category_id: int
    title: str
    slug: Optional[str] = None
    price: Decimal
    compare_at_price: Optional[Decimal]
    quantity: int
    status: ProductStatus
    rating: Decimal
    reviews_count: int
    images: List[ProductImageOut] = []
    flash_price: Optional[Decimal] = None


# ─────────────────────────────────────────────
# Cart
# ─────────────────────────────────────────────

class ProductVariantOut(OrmBase):
    id: int
    product_id: int
    sku: Optional[str]
    name: str
    price: Optional[Decimal]
    quantity: int
    is_active: bool
    sort_order: int


class CartItemCreate(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class CartItemOut(OrmBase):
    id: int
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    product: ProductListOut
    variant: Optional[ProductVariantOut] = None


# ─────────────────────────────────────────────
# Order
# ─────────────────────────────────────────────

class OrderItemOut(OrmBase):
    id: int
    product_id: int
    variant_id: Optional[int] = None
    variant_name: Optional[str] = None
    shop_id: int
    quantity: int
    price_at_time: Decimal
    commission_percent_used: Decimal
    platform_fee: Decimal
    seller_net: Decimal
    payout_status: str
    product: ProductListOut


class DeliveryInfoOut(OrmBase):
    id: int
    delivery_service: str
    tracking_number: Optional[str]
    cost: Decimal
    estimated_days: int
    city_from: str
    city_to: str
    address: str
    shipped_at: Optional[datetime]
    delivered_at: Optional[datetime]


class OrderCreate(BaseModel):
    delivery_address: str
    city_to: str
    delivery_service: str = "cdek"
    coupon_code: Optional[str] = None
    bonus_to_use: Decimal = Field(default=Decimal("0"), ge=0)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    tracking_number: Optional[str] = None


class OrderOut(OrmBase):
    id: int
    buyer_id: int
    total_price: Decimal
    subtotal: Decimal
    delivery_cost: Decimal
    platform_fee: Decimal
    seller_net: Decimal
    commission_percent_used: Decimal
    bonus_used: Decimal
    coupon_discount: Decimal
    status: OrderStatus
    delivery_address: str
    items: List[OrderItemOut] = []
    payment: Optional["PaymentOut"] = None
    delivery_info: Optional[DeliveryInfoOut] = None
    created_at: datetime
    updated_at: datetime


# ─────────────────────────────────────────────
# Payment
# ─────────────────────────────────────────────

class PaymentOut(OrmBase):
    id: int
    order_id: int
    gateway: PaymentGateway
    gateway_payment_id: Optional[str]
    amount: Decimal
    status: PaymentStatus
    confirmation_url: Optional[str]
    paid_at: Optional[datetime]


# ─────────────────────────────────────────────
# Fiscalization (54-ФЗ)
# ─────────────────────────────────────────────

class FiscalReceiptOut(OrmBase):
    id: int
    order_id: int
    payment_id: Optional[int]
    type: FiscalReceiptType
    status: FiscalReceiptStatus
    customer_contact: str
    total: Decimal
    tax_system_code: Optional[int]
    items: List[dict] = []
    fiscal_document_number: Optional[str]
    fiscal_storage_number: Optional[str]
    fiscal_attribute: Optional[str]
    registered_at: Optional[datetime]
    error: Optional[str]
    created_at: datetime


OrderOut.model_rebuild()


# ─────────────────────────────────────────────
# Review
# ─────────────────────────────────────────────

class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: Optional[str] = None
    photos: list[str] = Field(default_factory=list)


class ReviewModerationUpdate(BaseModel):
    status: ReviewStatus
    moderation_reason: Optional[str] = None


class ReviewReplyCreate(BaseModel):
    text: str = Field(min_length=2)


class ReviewReplyOut(OrmBase):
    id: int
    review_id: int
    seller_id: int
    text: str
    created_at: datetime
    updated_at: datetime


class ReviewOut(OrmBase):
    id: int
    user_id: int
    product_id: int
    rating: int
    text: Optional[str]
    status: ReviewStatus
    moderation_reason: Optional[str]
    helpful_count: int
    is_verified_purchase: bool = False
    created_at: datetime
    user: UserProfile
    reply: Optional[ReviewReplyOut] = None
    voted_by_me: bool = False
    photos: list["ReviewPhotoOut"] = Field(default_factory=list)


class ShopRatingSummary(BaseModel):
    shop_id: int
    rating: float
    reviews_count: int
    verified_count: int
    distribution: dict[str, int]


# ─────────────────────────────────────────────
# Coupon
# ─────────────────────────────────────────────

class CouponCreate(BaseModel):
    code: str
    discount_type: DiscountType
    discount_value: Decimal = Field(gt=0)
    valid_from: datetime
    valid_until: datetime
    max_uses: int = 0
    min_order_amount: Decimal = Decimal("0.00")
    is_active: bool = True


class CouponOut(OrmBase):
    id: int
    code: str
    discount_type: DiscountType
    discount_value: Decimal
    valid_from: datetime
    valid_until: datetime
    max_uses: int
    used_count: int
    min_order_amount: Decimal
    is_active: bool


class CouponValidateOut(BaseModel):
    valid: bool
    discount: Decimal
    message: str


# ─────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────

class ReportCreate(BaseModel):
    target_type: str = Field(pattern="^(product|shop|user)$")
    target_id: int
    reason: str = Field(min_length=10)


class ReportUpdate(BaseModel):
    status: ReportStatus
    resolution: Optional[str] = None
    moderator_id: Optional[int] = None


class ReportOut(OrmBase):
    id: int
    reporter_id: int
    target_type: str
    target_id: int
    reason: str
    status: ReportStatus
    moderator_id: Optional[int]
    resolution: Optional[str]
    created_at: datetime


# ─────────────────────────────────────────────
# Referral
# ─────────────────────────────────────────────

class ReferralOut(OrmBase):
    id: int
    referrer_id: int
    referred_user_id: int
    type: ReferralType
    code: str
    reward_paid: bool
    created_at: datetime


# ─────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────

class SettingOut(BaseModel):
    key: str
    value: str
    description: Optional[str]
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: str


class BulkSettingsUpdate(BaseModel):
    settings: dict[str, str]


# ─────────────────────────────────────────────
# Delivery calculation
# ─────────────────────────────────────────────

class DeliveryCalculateRequest(BaseModel):
    city_from: str = "Москва"
    city_to: str
    weight_g: int = 500
    service: str = "cdek"


class DeliveryCalculateResponse(BaseModel):
    cost: Decimal
    estimated_days: int
    service: str


class DeliveryServiceOut(BaseModel):
    code: str
    name: str


class DeliveryQuoteOut(BaseModel):
    """A single service's quote when comparing all delivery options at once."""
    code: str
    name: str
    cost: Decimal
    estimated_days: int


class PickupPointOut(BaseModel):
    code: str
    name: str
    address: str
    city: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    work_time: Optional[str] = None


# ─────────────────────────────────────────────
# Pagination helper
# ─────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int


# ─────────────────────────────────────────────
# Dashboard stats (admin)
# ─────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_orders: int
    orders_today: int
    total_revenue: Decimal
    revenue_today: Decimal
    total_users: int
    new_users_today: int
    total_products: int
    pending_moderation: int
    open_reports: int


class BalanceTransactionOut(OrmBase):
    id: int
    user_id: int
    change: Decimal
    type: BalanceTransactionType
    reference_type: Optional[str]
    reference_id: Optional[int]
    description: Optional[str]
    balance_after: Decimal
    created_at: datetime


# ─────────────────────────────────────────────
# Seller plans & subscriptions
# ─────────────────────────────────────────────

class SellerPlanCreate(BaseModel):
    name: str = Field(min_length=2)
    description: Optional[str] = None
    monthly_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    commission_percent: Decimal = Field(ge=0, le=100)
    trial_days: int = Field(default=0, ge=0)
    is_active: bool = True
    is_default: bool = False
    sort_order: int = 0


class SellerPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    monthly_price: Optional[Decimal] = Field(None, ge=0)
    commission_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    trial_days: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    sort_order: Optional[int] = None


class SellerPlanOut(OrmBase):
    id: int
    name: str
    description: Optional[str]
    monthly_price: Decimal
    commission_percent: Decimal
    trial_days: int
    is_active: bool
    is_default: bool
    sort_order: int


class SellerSubscriptionOut(OrmBase):
    id: int
    shop_id: int
    plan_id: int
    status: str
    current_period_end: Optional[datetime]
    trial_used: bool
    auto_renew: bool
    plan: SellerPlanOut


class SubscribeRequest(BaseModel):
    plan_id: int
    pay_from_balance: bool = True


# ─────────────────────────────────────────────
# Block 1: Variants, attributes, questions, review photos
# ─────────────────────────────────────────────

class ProductVariantCreate(BaseModel):
    sku: Optional[str] = None
    name: str = Field(min_length=1)
    price: Optional[Decimal] = Field(None, ge=0)
    quantity: int = Field(default=0, ge=0)
    is_active: bool = True
    sort_order: int = 0


class AttributeCreate(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    is_filterable: bool = True
    sort_order: int = 0


class AttributeOut(OrmBase):
    id: int
    name: str
    slug: str
    is_filterable: bool
    sort_order: int


class ProductAttributeValueIn(BaseModel):
    attribute_id: int
    value: str


class ProductAttributeValueOut(OrmBase):
    id: int
    attribute_id: int
    value: str
    attribute: AttributeOut


class ProductQuestionCreate(BaseModel):
    question: str = Field(min_length=3)


class ProductAnswerCreate(BaseModel):
    answer: str = Field(min_length=1)


class ProductQuestionOut(OrmBase):
    id: int
    product_id: int
    user_id: int
    question: str
    answer: Optional[str]
    answered_at: Optional[datetime]
    created_at: datetime
    user: UserProfile


class ReviewPhotoOut(OrmBase):
    id: int
    url: str
    sort_order: int


ReviewOut.model_rebuild()


# ─────────────────────────────────────────────
# Block 2: Notifications & chat
# ─────────────────────────────────────────────

class NotificationOut(OrmBase):
    id: int
    type: str
    title: str
    body: Optional[str]
    link: Optional[str]
    is_read: bool
    created_at: datetime


class ChatMessageOut(OrmBase):
    id: int
    thread_id: int
    sender_id: int
    text: str
    is_read: bool
    created_at: datetime


class ChatMessageCreate(BaseModel):
    text: str = Field(min_length=1)


class ChatThreadOut(OrmBase):
    id: int
    buyer_id: int
    shop_id: int
    created_at: datetime
    updated_at: datetime


class StartChatRequest(BaseModel):
    shop_id: int
    text: str = Field(min_length=1)


# ─────────────────────────────────────────────
# Block 3: Seller coupons & payouts
# ─────────────────────────────────────────────

class SellerCouponCreate(BaseModel):
    code: str = Field(min_length=2)
    discount_type: DiscountType = DiscountType.percent
    discount_value: Decimal = Field(ge=0)
    min_order_amount: Decimal = Field(default=Decimal("0"), ge=0)
    usage_limit: Optional[int] = None
    expires_at: Optional[datetime] = None


class SellerCouponOut(OrmBase):
    id: int
    shop_id: int
    code: str
    discount_type: DiscountType
    discount_value: Decimal
    min_order_amount: Decimal
    usage_limit: Optional[int]
    used_count: int
    is_active: bool
    expires_at: Optional[datetime]


class PayoutRequestCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    payout_details: str = Field(min_length=4)


class PayoutRequestOut(OrmBase):
    id: int
    user_id: int
    amount: Decimal
    status: str
    payout_details: str
    admin_comment: Optional[str]
    processed_at: Optional[datetime]
    created_at: datetime


class PayoutProcessRequest(BaseModel):
    status: str  # approved | rejected | paid
    admin_comment: Optional[str] = None


# ─────────────────────────────────────────────
# Block 5: Homepage banners
# ─────────────────────────────────────────────

class HomepageBannerCreate(BaseModel):
    title: str = Field(min_length=1)
    subtitle: Optional[str] = None
    image_url: str = Field(min_length=1)
    link: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class HomepageBannerOut(OrmBase):
    id: int
    title: str
    subtitle: Optional[str]
    image_url: str
    link: Optional[str]
    is_active: bool
    sort_order: int


# ─────────────────────────────────────────────
# Items 1-3: Returns, sub-orders
# ─────────────────────────────────────────────

class ReturnRequestCreate(BaseModel):
    order_item_id: int
    quantity: int = Field(default=1, ge=1)
    reason: str = Field(min_length=5)


class ReturnRequestOut(OrmBase):
    id: int
    order_item_id: int
    buyer_id: int
    shop_id: int
    quantity: int
    reason: str
    status: str
    refund_amount: Decimal
    resolution_comment: Optional[str]
    processed_at: Optional[datetime]
    created_at: datetime


class ReturnProcessRequest(BaseModel):
    status: str  # approved | rejected | in_transit | refunded
    resolution_comment: Optional[str] = None
    refund_amount: Optional[Decimal] = Field(None, ge=0)


class SubOrderOut(OrmBase):
    id: int
    order_id: int
    shop_id: int
    status: str
    tracking_number: Optional[str]
    delivery_service: Optional[str]


class SubOrderStatusUpdate(BaseModel):
    status: str  # processing | shipped | delivered | completed | cancelled
    tracking_number: Optional[str] = None


# ─────────────────────────────────────────────
# Item 7: Product subscriptions (back-in-stock / price-drop)
# ─────────────────────────────────────────────

class ProductSubscriptionCreate(BaseModel):
    product_id: int
    kind: str  # back_in_stock | price_drop
    target_price: Optional[Decimal] = Field(None, ge=0)


class ProductSubscriptionOut(OrmBase):
    id: int
    product_id: int
    kind: str
    target_price: Optional[Decimal]
    is_notified: bool
    created_at: datetime


# ─────────────────────────────────────────────
# Item 11: Currencies
# ─────────────────────────────────────────────

class CurrencyRateOut(OrmBase):
    code: str
    rate: Decimal
    symbol: str


class CurrencyRateUpsert(BaseModel):
    code: str
    rate: Decimal = Field(gt=0)
    symbol: str


# ─────────────────────────────────────────────
# Item 8: 2FA
# ─────────────────────────────────────────────

class TwoFASetupOut(BaseModel):
    secret: str
    otpauth_url: str
    backup_codes: list[str]


class TwoFAVerifyRequest(BaseModel):
    code: str


class TwoFALoginRequest(BaseModel):
    email: str
    password: str
    code: str


# ─────────────────────────────────────────────
# Block 2: addresses, wishlists, browsing history
# ─────────────────────────────────────────────

class AddressCreate(BaseModel):
    label: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    phone: str = Field(min_length=5)
    city: str = Field(min_length=1)
    street: str = Field(min_length=1)
    building: Optional[str] = None
    apartment: Optional[str] = None
    postal_code: Optional[str] = None
    is_default: bool = False


class AddressOut(OrmBase):
    id: int
    label: str
    full_name: str
    phone: str
    city: str
    street: str
    building: Optional[str]
    apartment: Optional[str]
    postal_code: Optional[str]
    is_default: bool
    created_at: datetime


class WishlistCollectionCreate(BaseModel):
    name: str = Field(min_length=1)
    is_public: bool = False


class WishlistItemOut(OrmBase):
    id: int
    product_id: int
    added_at: datetime
    product: ProductListOut


class WishlistCollectionOut(OrmBase):
    id: int
    name: str
    is_public: bool
    created_at: datetime
    items: list[WishlistItemOut] = Field(default_factory=list)


class WishlistCollectionBrief(OrmBase):
    id: int
    name: str
    is_public: bool
    created_at: datetime
    item_count: int = 0


# ─────────────────────────────────────────────
# Block 3: stock movements, flash sales, bulk ops
# ─────────────────────────────────────────────

class StockMovementOut(OrmBase):
    id: int
    product_id: int
    variant_id: Optional[int]
    change: int
    reason: str
    quantity_after: int
    note: Optional[str]
    created_at: datetime


class StockAdjustRequest(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    change: int  # positive = restock, negative = manual removal
    note: Optional[str] = None


class LowStockItem(BaseModel):
    product_id: int
    title: str
    quantity: int
    threshold: int


class FlashSaleCreate(BaseModel):
    product_id: int
    discount_percent: Decimal = Field(gt=0, le=99)
    starts_at: datetime
    ends_at: datetime


class FlashSaleOut(OrmBase):
    id: int
    product_id: int
    shop_id: int
    discount_percent: Decimal
    starts_at: datetime
    ends_at: datetime
    is_active: bool
    created_at: datetime


class FlashSaleWithProduct(FlashSaleOut):
    product_title: Optional[str] = None
    base_price: Optional[Decimal] = None
    effective_price: Optional[Decimal] = None
    is_running: bool = False


class BulkPriceUpdate(BaseModel):
    product_ids: list[int]
    # Exactly one of these strategies:
    set_price: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None  # e.g. -10 => -10%


class BulkStatusUpdate(BaseModel):
    product_ids: list[int]
    is_active: bool


# ─────────────────────────────────────────────
# Block 4: moderation queue, audit log, auto-flags
# ─────────────────────────────────────────────

class AuditLogOut(OrmBase):
    id: int
    actor_id: Optional[int]
    actor_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[int]
    detail: Optional[str]
    created_at: datetime


class ModerationQueueItem(BaseModel):
    product_id: int
    title: str
    shop_id: int
    shop_name: Optional[str] = None
    price: Decimal
    created_at: datetime
    priority: int = 0           # higher = needs attention sooner
    flags: list[str] = Field(default_factory=list)  # auto-flag reasons


class BulkModerateRequest(BaseModel):
    product_ids: list[int]
    action: str                 # approve | reject
    reason: Optional[str] = None


# ─────────────────────────────────────────────
# Block 5: cohort analytics, RBAC, reconciliation, feature flags
# ─────────────────────────────────────────────

class FeatureFlagOut(OrmBase):
    id: int
    key: str
    description: Optional[str]
    is_enabled: bool
    rollout_percent: int
    updated_at: datetime


class FeatureFlagUpsert(BaseModel):
    key: str = Field(min_length=1)
    description: Optional[str] = None
    is_enabled: bool = False
    rollout_percent: int = Field(default=100, ge=0, le=100)


class UserPermissionsUpdate(BaseModel):
    permissions: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────
# Block 6: chat templates, business hours, file upload
# ─────────────────────────────────────────────

class ChatTemplateCreate(BaseModel):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class ChatTemplateOut(OrmBase):
    id: int
    title: str
    body: str
    created_at: datetime


class BusinessHoursUpdate(BaseModel):
    business_hours: Optional[str] = None


class FileUploadResponse(BaseModel):
    url: str
    filename: str


# ─────────────────────────────────────────────
# Email/phone verification
# ─────────────────────────────────────────────

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)


class ResendCodeRequest(BaseModel):
    email: EmailStr


class VerifyPhoneRequest(BaseModel):
    code: str = Field(min_length=4, max_length=8)


# ─────────────────────────────────────────────
# Block B: seller tax regime & requisites
# ─────────────────────────────────────────────

class SellerRequisitesCreate(BaseModel):
    tax_regime: str  # self_employed | individual | company
    legal_name: str = Field(min_length=2, max_length=255)
    inn: str = Field(min_length=10, max_length=12)
    ogrn: Optional[str] = Field(None, max_length=15)
    kpp: Optional[str] = Field(None, max_length=9)
    legal_address: Optional[str] = Field(None, max_length=500)
    bank_account: Optional[str] = Field(None, max_length=20)
    bank_name: Optional[str] = Field(None, max_length=255)
    bik: Optional[str] = Field(None, max_length=9)
    corr_account: Optional[str] = Field(None, max_length=20)
    # Фискализация (54-ФЗ): необязательные; при отсутствии берутся настройки платформы.
    vat_code: Optional[int] = Field(None, ge=1, le=6)
    tax_system_code: Optional[int] = Field(None, ge=1, le=6)

    @field_validator("tax_regime")
    @classmethod
    def _valid_regime(cls, v: str) -> str:
        if v not in ("self_employed", "individual", "company"):
            raise ValueError("Недопустимый налоговый режим")
        return v

    @model_validator(mode="after")
    def _check_required_by_regime(self):
        """
        Enforce the documents required for each regime:
        - self_employed: ИНН (12 цифр) — минимум
        - individual (ИП): ИНН + ОГРНИП
        - company (ООО): ИНН (10) + ОГРН + КПП + юр.адрес
        """
        regime = self.tax_regime
        if regime == "individual":
            if not self.ogrn:
                raise ValueError("Для ИП обязателен ОГРНИП")
        elif regime == "company":
            missing = []
            if not self.ogrn:
                missing.append("ОГРН")
            if not self.kpp:
                missing.append("КПП")
            if not self.legal_address:
                missing.append("юридический адрес")
            if missing:
                raise ValueError("Для ООО обязательны: " + ", ".join(missing))
        # Digits-only sanity checks
        if not self.inn.isdigit():
            raise ValueError("ИНН должен состоять только из цифр")
        return self


class SellerRequisitesOut(OrmBase):
    id: int
    shop_id: int
    tax_regime: str
    legal_name: str
    inn: str
    ogrn: Optional[str]
    kpp: Optional[str]
    legal_address: Optional[str]
    bank_account: Optional[str]
    bank_name: Optional[str]
    bik: Optional[str]
    corr_account: Optional[str]
    vat_code: Optional[int]
    tax_system_code: Optional[int]
    created_at: datetime


class ShopCreateWithRequisites(BaseModel):
    """Shop creation payload that bundles the required seller requisites."""
    name: str = Field(min_length=2)
    description: Optional[str] = None
    requisites: SellerRequisitesCreate


# ─────────────────────────────────────────────
# Support (tickets & chat)
# ─────────────────────────────────────────────

from app.models.models import SupportTicketStatus, SupportTicketPriority  # noqa: E402


class SupportTicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    message: str = Field(min_length=1, max_length=5000)
    category: Optional[str] = Field(None, max_length=40)
    priority: Optional[SupportTicketPriority] = None


class SupportMessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    attachment_url: Optional[str] = Field(None, max_length=512)


class SupportMessageOut(OrmBase):
    id: int
    ticket_id: int
    sender_id: int
    is_staff: bool
    text: str
    attachment_url: Optional[str]
    created_at: datetime


class SupportTicketOut(OrmBase):
    id: int
    user_id: int
    subject: str
    category: Optional[str]
    status: SupportTicketStatus
    priority: SupportTicketPriority
    assigned_to_id: Optional[int]
    is_overdue: bool = False
    last_message_at: datetime
    created_at: datetime


class SupportTicketDetailOut(SupportTicketOut):
    user: UserProfile
    assigned_to: Optional[UserProfile] = None
    messages: list[SupportMessageOut] = Field(default_factory=list)


class SupportTicketUpdate(BaseModel):
    status: Optional[SupportTicketStatus] = None
    priority: Optional[SupportTicketPriority] = None
    assigned_to_id: Optional[int] = None


class SupportStats(BaseModel):
    open: int
    in_progress: int
    pending_user: int
    resolved_today: int
    closed: int
    unassigned: int
    overdue: int
    avg_first_response_minutes: Optional[float]
    by_priority: dict[str, int]


class SupportUserView(BaseModel):
    """Read-only 360° view of a user for support/moderator staff."""
    id: int
    email: str
    full_name: str
    phone: Optional[str]
    role: UserRole
    is_active: bool
    balance: Decimal
    bonus_balance: Decimal
    created_at: datetime
    orders_count: int
    tickets_count: int
    is_seller: bool
    shop_id: Optional[int] = None
    shop_name: Optional[str] = None


# ─────────────────────────────────────────────
# Paid features & promotion (auction)
# ─────────────────────────────────────────────

from app.models.models import PromotionStatus, PaidFeaturePricing  # noqa: E402


class PaidFeatureOut(OrmBase):
    id: int
    key: str
    name: str
    description: Optional[str]
    placement: str
    pricing_mode: PaidFeaturePricing
    price: Decimal
    billing_period: str
    slots: int
    is_enabled: bool


class PaidFeatureUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    slots: Optional[int] = Field(None, ge=0)
    is_enabled: Optional[bool] = None
    billing_period: Optional[str] = None


class PromotionCreate(BaseModel):
    feature_key: str
    bid_amount: Decimal = Field(gt=0)
    product_id: Optional[int] = None


class PromotionOut(OrmBase):
    id: int
    shop_id: int
    product_id: Optional[int]
    feature_key: str
    placement: str
    bid_amount: Decimal
    status: PromotionStatus
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    total_spent: Decimal
    created_at: datetime


class AuctionStanding(BaseModel):
    feature_key: str
    slots: int
    bidders: int
    reserve: str
    min_winning_bid: str


# ─────────────────────────────────────────────
# Promo rules & bundles (advanced promotions)
# ─────────────────────────────────────────────

from app.models.models import PromoType  # noqa: E402


class PromoTier(BaseModel):
    min_qty: int = Field(ge=1)
    percent: Decimal = Field(gt=0, le=100)


class PromoRuleCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    type: PromoType
    is_active: bool = True
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    product_id: Optional[int] = None
    category_id: Optional[int] = None
    buy_quantity: int = 0
    free_quantity: int = 0
    tiers: list[PromoTier] = Field(default_factory=list)


class PromoRuleUpdate(BaseModel):
    title: Optional[str] = None
    is_active: Optional[bool] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    buy_quantity: Optional[int] = None
    free_quantity: Optional[int] = None
    tiers: Optional[list[PromoTier]] = None


class PromoRuleOut(OrmBase):
    id: int
    shop_id: int
    title: str
    type: PromoType
    is_active: bool
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    product_id: Optional[int]
    category_id: Optional[int]
    buy_quantity: int
    free_quantity: int
    tiers: list[dict] = []
    created_at: datetime


class BundleItemIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class BundleCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    description: Optional[str] = None
    bundle_price: Decimal = Field(gt=0)
    is_active: bool = True
    items: list[BundleItemIn] = Field(min_length=2)


class BundleItemOut(OrmBase):
    id: int
    product_id: int
    quantity: int


class BundleOut(OrmBase):
    id: int
    shop_id: int
    title: str
    description: Optional[str]
    bundle_price: Decimal
    is_active: bool
    items: list[BundleItemOut] = []
    created_at: datetime


class CartPromoSummary(BaseModel):
    subtotal: Decimal
    promo_discount: Decimal
    breakdown: list[dict]
    estimated_total: Decimal


# ─────────────────────────────────────────────
# Disputes (arbitration)
# ─────────────────────────────────────────────

from app.models.models import DisputeStatus, DisputeResolution  # noqa: E402


class DisputeCreate(BaseModel):
    order_id: int
    subject: str = Field(min_length=3, max_length=200)
    reason: str = Field(min_length=5, max_length=5000)
    order_item_id: Optional[int] = None


class DisputeMessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class DisputeMessageOut(OrmBase):
    id: int
    sender_id: int
    sender_role: str
    text: str
    created_at: datetime


class DisputeOut(OrmBase):
    id: int
    order_id: int
    order_item_id: Optional[int]
    buyer_id: int
    shop_id: int
    opened_by: str
    subject: str
    status: DisputeStatus
    resolution: DisputeResolution
    refund_amount: Optional[Decimal]
    mediator_id: Optional[int]
    last_message_at: datetime
    created_at: datetime


class DisputeDetailOut(DisputeOut):
    reason: str
    resolution_note: Optional[str] = None
    buyer: Optional[UserProfile] = None
    messages: list[DisputeMessageOut] = Field(default_factory=list)


class DisputeResolve(BaseModel):
    resolution: DisputeResolution
    refund_amount: Optional[Decimal] = Field(None, ge=0)
    note: Optional[str] = None


# ─────────────────────────────────────────────
# Gift certificates & promo balance
# ─────────────────────────────────────────────

from app.models.models import GiftCertificateStatus  # noqa: E402


class GiftPurchase(BaseModel):
    amount: Decimal = Field(gt=0)
    recipient_email: Optional[str] = None
    message: Optional[str] = Field(None, max_length=500)


class GiftRedeem(BaseModel):
    code: str = Field(min_length=4, max_length=32)


class GiftCertificateOut(OrmBase):
    id: int
    code: str
    amount: Decimal
    status: GiftCertificateStatus
    recipient_email: Optional[str]
    message: Optional[str]
    created_at: datetime


class AdminGiftIssue(BaseModel):
    amount: Decimal = Field(gt=0)
    count: int = Field(default=1, ge=1, le=500)
    message: Optional[str] = None
    expires_at: Optional[datetime] = None


# ─────────────────────────────────────────────
# Loyalty tiers
# ─────────────────────────────────────────────

class LoyaltyTierOut(OrmBase):
    id: int
    key: str
    name: str
    level: int
    min_spend: Decimal
    cashback_percent: Decimal
    free_shipping: bool
    perks: Optional[str]
    color: Optional[str]
    retention_days: int
    is_active: bool


class LoyaltyTierCreate(BaseModel):
    key: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=80)
    level: int = Field(ge=1)
    min_spend: Decimal = Field(ge=0)
    cashback_percent: Decimal = Field(ge=0, le=100)
    free_shipping: bool = False
    perks: Optional[str] = None
    color: Optional[str] = None
    retention_days: int = Field(default=0, ge=0)
    is_active: bool = True


class LoyaltyTierUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[int] = None
    min_spend: Optional[Decimal] = Field(None, ge=0)
    cashback_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    free_shipping: Optional[bool] = None
    perks: Optional[str] = None
    color: Optional[str] = None
    retention_days: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

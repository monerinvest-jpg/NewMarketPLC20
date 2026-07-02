"""
Catalog: categories, products, variants/attributes, reviews, wishlists, stock, flash sales.

Split out of the former monolithic models.py; import via app.models.models
(the re-export hub) or directly from this module.
"""
from app.models._base import *  # noqa: F401,F403 — shared imports/Enum/utcnow
from app.models._base import Enum, utcnow  # noqa: F401 — explicit for linters


class ProductStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    rejected = "rejected"
    blocked = "blocked"


class ProductType(str, enum.Enum):
    """What kind of product this is, which drives fulfillment.

    physical — shippable goods (stock, weight, delivery, sub-orders);
    digital  — a downloadable file delivered instantly after payment;
    course   — access to an on-platform learning course (LMS).
    """
    physical = "physical"
    digital = "digital"
    course = "course"


class CategoryKind(str, enum.Enum):
    """Optional hint on a category subtree so the seller product form and the
    storefront know what kind of products live under it. Null = generic."""
    physical = "physical"
    digital = "digital"
    course = "course"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("category.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    image: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Optional kind hint for the subtree (physical/digital/course); null = generic.
    kind: Mapped[Optional[CategoryKind]] = mapped_column(Enum(CategoryKind), nullable=True)

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
    # Fulfillment kind. physical (default) ships and tracks stock; digital is
    # delivered instantly as a file; course grants LMS access. For digital/course
    # the quantity/weight/delivery fields are ignored (unlimited stock).
    product_type: Mapped[ProductType] = mapped_column(
        Enum(ProductType), default=ProductType.physical, nullable=False, server_default="physical"
    )
    status: Mapped[ProductStatus] = mapped_column(Enum(ProductStatus), default=ProductStatus.pending, nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.00"), nullable=False)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    views_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Provenance for products imported from external platforms (e.g. VK Market):
    # source='vk', external_id=<vk item id>. Re-import upserts by this pair
    # instead of duplicating (see uq_product_shop_source_external).
    source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
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
    digital_assets: Mapped[List["DigitalAsset"]] = relationship("DigitalAsset", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_product_shop_id", "shop_id"),
        Index("ix_product_category_id", "category_id"),
        Index("ix_product_status", "status"),
        Index("ix_product_price", "price"),
        Index("ix_product_rating", "rating"),
        Index("ix_product_title", "title"),
        UniqueConstraint("shop_id", "source", "external_id", name="uq_product_shop_source_external"),
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
    """A photo OR video attached to a product review (media_type discriminates)."""
    __tablename__ = "review_photo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("review.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    media_type: Mapped[str] = mapped_column(String(10), default="image", nullable=False, server_default="image")  # image | video
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    review: Mapped["Review"] = relationship("Review", back_populates="photos")

    __table_args__ = (
        Index("ix_review_photo_review_id", "review_id"),
    )


# ─── Block 2: Notifications & buyer-seller chat ─────────────────────────────────


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

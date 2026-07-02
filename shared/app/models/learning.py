"""
Digital goods & LMS: courses, lessons, progress, certificates, digital assets, entitlements.

Split out of the former monolithic models.py; import via app.models.models
(the re-export hub) or directly from this module.
"""
from app.models._base import *  # noqa: F401,F403 — shared imports/Enum/utcnow
from app.models._base import Enum, utcnow  # noqa: F401 — explicit for linters


class LessonType(str, enum.Enum):
    """Kind of content in a course lesson."""
    video = "video"   # private video file, streamed to entitled buyers
    pdf = "pdf"       # private PDF, shown in the protected reader
    text = "text"     # inline rich text/HTML stored in the DB
    quiz = "quiz"     # graded questions; quiz_json holds questions + answer key


class DigitalAsset(Base):
    """A downloadable file belonging to a digital product.

    Files are stored PRIVATELY (object-storage key or a non-public local path),
    never under the public /uploads mount. Entitled buyers receive a short-lived
    signed URL (or a streamed response) instead of a permanent link.
    """
    __tablename__ = "digital_asset"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)        # original name shown to buyer
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)      # private key/path, NOT a public URL
    content_type: Mapped[str] = mapped_column(String(120), nullable=False, server_default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="digital_assets")

    __table_args__ = (
        Index("ix_digital_asset_product_id", "product_id"),
    )


class Entitlement(Base):
    """A buyer's right to access a digital product (or course) after purchase.

    Granted when the order's payment succeeds; checked on every download/stream.
    Unique per (user, product, order) so re-delivery of a payment webhook never
    creates duplicate grants. `revoked` is set on refund/chargeback.
    """
    __tablename__ = "entitlement"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("order.id"), nullable=False)
    order_item_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("order_item.id"), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User")
    product: Mapped["Product"] = relationship("Product")
    order: Mapped["Order"] = relationship("Order")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", "order_id", name="uq_entitlement_user_product_order"),
        Index("ix_entitlement_user_id", "user_id"),
        Index("ix_entitlement_product_id", "product_id"),
    )


class Course(Base):
    """The LMS structure of a course-type product. One Course per course Product.

    Access is governed by the buyer's Entitlement to `product_id` (granted on
    purchase), so courses reuse the same purchase/payment flow as digital goods.
    """
    __tablename__ = "course"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False, unique=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shop.id"), nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)        # beginner/intermediate/advanced
    language: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    intro_video_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # private promo video
    # Certificate customization (seller-controlled)
    cert_instructor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # instructor / signatory name
    cert_logo_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)    # private logo image key
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    product: Mapped["Product"] = relationship("Product")
    modules: Mapped[List["CourseModule"]] = relationship(
        "CourseModule", back_populates="course", cascade="all, delete-orphan",
        order_by="CourseModule.sort_order",
    )

    __table_args__ = (
        Index("ix_course_shop_id", "shop_id"),
    )


class CourseModule(Base):
    """A section of a course, grouping lessons."""
    __tablename__ = "course_module"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("course.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    course: Mapped["Course"] = relationship("Course", back_populates="modules")
    lessons: Mapped[List["CourseLesson"]] = relationship(
        "CourseLesson", back_populates="module", cascade="all, delete-orphan",
        order_by="CourseLesson.sort_order",
    )

    __table_args__ = (
        Index("ix_course_module_course_id", "course_id"),
    )


class CourseLesson(Base):
    """A single lesson: a private video/PDF file or inline text.

    Video/PDF files are stored privately (same storage as digital assets) and
    delivered only to entitled buyers via a gated stream — never a public URL.
    `is_preview` lessons are free to watch before purchase.
    """
    __tablename__ = "course_lesson"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("course_module.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("course.id"), nullable=False)  # denormalised
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    lesson_type: Mapped[LessonType] = mapped_column(Enum(LessonType), nullable=False)
    # video/pdf: private storage key + content type; text: text_body holds HTML.
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    text_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # quiz lessons: JSON {"pass_score": 70, "questions": [{"q","options":[...],"correct":idx}]}.
    # The answer key (correct indices) is stripped before sending to buyers.
    quiz_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Set once a video lesson has been packaged into encrypted HLS (AES-128). The
    # HLS files live privately under "hls/<lesson_id>/" and are served gated.
    hls_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    module: Mapped["CourseModule"] = relationship("CourseModule", back_populates="lessons")

    __table_args__ = (
        Index("ix_course_lesson_module_id", "module_id"),
        Index("ix_course_lesson_course_id", "course_id"),
    )


class LessonProgress(Base):
    """A buyer's completion state for a lesson, for progress tracking."""
    __tablename__ = "lesson_progress"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    lesson_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("course_lesson.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("course.id"), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress_user_lesson"),
        Index("ix_lesson_progress_user_course", "user_id", "course_id"),
    )


class QuizAttempt(Base):
    """A buyer's attempt at a quiz lesson (kept for history; latest pass completes the lesson)."""
    __tablename__ = "quiz_attempt"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    lesson_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("course_lesson.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("course.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)       # percent 0..100
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    answers_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)     # submitted answers snapshot
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_quiz_attempt_user_lesson", "user_id", "lesson_id"),
    )


class Certificate(Base):
    """Completion certificate issued once a buyer finishes 100% of a course."""
    __tablename__ = "certificate"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("course.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)   # public verification code
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)     # snapshot at issue time
    course_title: Mapped[str] = mapped_column(String(512), nullable=False)       # snapshot
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_certificate_user_course"),
        Index("ix_certificate_code", "code"),
    )

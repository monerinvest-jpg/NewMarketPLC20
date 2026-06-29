"""
Completion certificates: issued once a buyer finishes 100% of a course,
rendered to a PDF (reportlab) and publicly verifiable by code.
"""
import io
import secrets
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Certificate, Course, Product, User
from app.services import course_service


def _gen_code() -> str:
    return "CERT-" + secrets.token_hex(8).upper()


async def is_eligible(db: AsyncSession, user_id: int, course_id: int) -> bool:
    return await course_service.course_progress_percent(db, user_id, course_id) >= 100


async def get_existing(db: AsyncSession, user_id: int, course_id: int) -> Optional[Certificate]:
    return (await db.execute(
        select(Certificate).where(
            Certificate.user_id == user_id, Certificate.course_id == course_id
        )
    )).scalar_one_or_none()


async def issue(
    db: AsyncSession, user: User, course: Course, product: Product,
    recipient_name: Optional[str] = None,
) -> Optional[Certificate]:
    """Issue (or return existing) certificate if the buyer completed the course.

    The buyer may supply their full name (ФИО) for the certificate; if a name is
    given it is used (and updates an existing certificate so typos can be fixed).
    """
    clean = (recipient_name or "").strip()
    existing = await get_existing(db, user.id, course.id)
    if existing:
        if clean and clean != existing.recipient_name:
            existing.recipient_name = clean
        return existing
    if not await is_eligible(db, user.id, course.id):
        return None
    cert = Certificate(
        user_id=user.id,
        course_id=course.id,
        product_id=product.id,
        code=_gen_code(),
        recipient_name=clean or (user.full_name or user.email),
        course_title=product.title,
    )
    db.add(cert)
    await db.flush()
    return cert


async def verify(db: AsyncSession, code: str) -> Optional[Certificate]:
    return (await db.execute(
        select(Certificate).where(Certificate.code == code)
    )).scalar_one_or_none()


# Registered font names (fall back to Helvetica if the Cyrillic TTF is absent —
# e.g. local dev without fonts-dejavu-core; the deployed image installs it).
_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_FONTS_READY = False


def _ensure_fonts() -> None:
    global _FONT, _FONT_BOLD, _FONTS_READY
    if _FONTS_READY:
        return
    _FONTS_READY = True
    import os
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        if os.path.isfile(regular) and os.path.isfile(bold):
            pdfmetrics.registerFont(TTFont("DejaVu", regular))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
            _FONT, _FONT_BOLD = "DejaVu", "DejaVu-Bold"
    except Exception:
        pass


def render_pdf(cert: Certificate, course: Optional[Course] = None) -> bytes:
    """Render an A4-landscape certificate (Russian, Cyrillic-capable) to PDF bytes.
    Includes the seller's logo and instructor/signature when customised on `course`."""
    _ensure_fonts()
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    # Border
    c.setLineWidth(3)
    c.setStrokeColorRGB(0.95, 0.45, 0.09)  # marketplace orange
    c.rect(15 * mm, 15 * mm, width - 30 * mm, height - 30 * mm)

    # Seller logo (top centre), if provided.
    if course is not None and getattr(course, "cert_logo_key", None):
        try:
            from app.services import digital_storage_service
            raw = digital_storage_service.read_bytes(course.cert_logo_key)
            if raw:
                img = ImageReader(io.BytesIO(raw))
                c.drawImage(img, width / 2 - 20 * mm, height - 45 * mm, width=40 * mm, height=22 * mm,
                            preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont(_FONT_BOLD, 32)
    c.drawCentredString(width / 2, height - 62 * mm, "СЕРТИФИКАТ")

    c.setFont(_FONT, 15)
    c.drawCentredString(width / 2, height - 82 * mm, "настоящим подтверждается, что")

    c.setFont(_FONT_BOLD, 26)
    c.drawCentredString(width / 2, height - 100 * mm, cert.recipient_name)

    c.setFont(_FONT, 15)
    c.drawCentredString(width / 2, height - 116 * mm, "успешно прошёл(а) курс")

    c.setFont(_FONT_BOLD, 19)
    c.drawCentredString(width / 2, height - 131 * mm, cert.course_title)

    # Instructor / signature (bottom right), if provided.
    if course is not None and getattr(course, "cert_instructor", None):
        c.setFont(_FONT, 12)
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.drawRightString(width - 30 * mm, 40 * mm, course.cert_instructor)
        c.setStrokeColorRGB(0.6, 0.6, 0.6)
        c.line(width - 75 * mm, 47 * mm, width - 25 * mm, 47 * mm)
        c.setFont(_FONT, 9)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawRightString(width - 30 * mm, 35 * mm, "Преподаватель")

    c.setFont(_FONT, 11)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    issued = cert.issued_at.strftime("%d.%m.%Y") if cert.issued_at else ""
    c.drawCentredString(width / 2, 25 * mm, f"Дата выдачи: {issued}    •    Код проверки: {cert.code}")

    c.showPage()
    c.save()
    return buf.getvalue()

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


async def issue(db: AsyncSession, user: User, course: Course, product: Product) -> Optional[Certificate]:
    """Issue (or return existing) certificate if the buyer completed the course."""
    existing = await get_existing(db, user.id, course.id)
    if existing:
        return existing
    if not await is_eligible(db, user.id, course.id):
        return None
    cert = Certificate(
        user_id=user.id,
        course_id=course.id,
        product_id=product.id,
        code=_gen_code(),
        recipient_name=user.full_name or user.email,
        course_title=product.title,
    )
    db.add(cert)
    await db.flush()
    return cert


async def verify(db: AsyncSession, code: str) -> Optional[Certificate]:
    return (await db.execute(
        select(Certificate).where(Certificate.code == code)
    )).scalar_one_or_none()


def render_pdf(cert: Certificate) -> bytes:
    """Render a simple A4-landscape certificate to PDF bytes."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    # Border
    c.setLineWidth(3)
    c.setStrokeColorRGB(0.95, 0.45, 0.09)  # marketplace orange
    c.rect(15 * mm, 15 * mm, width - 30 * mm, height - 30 * mm)

    c.setFont("Helvetica-Bold", 34)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawCentredString(width / 2, height - 55 * mm, "CERTIFICATE OF COMPLETION")

    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 80 * mm, "This certifies that")

    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width / 2, height - 98 * mm, cert.recipient_name)

    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 115 * mm, "has successfully completed the course")

    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 130 * mm, cert.course_title)

    c.setFont("Helvetica", 11)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    issued = cert.issued_at.strftime("%d.%m.%Y") if cert.issued_at else ""
    c.drawCentredString(width / 2, 30 * mm, f"Issued: {issued}    •    Verification code: {cert.code}")

    c.showPage()
    c.save()
    return buf.getvalue()

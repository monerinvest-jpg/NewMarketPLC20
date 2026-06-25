"""
Shipping label generator. Produces a compact A6 PDF label with sender,
recipient, parcel info and a Code128 barcode of the tracking number. Used as a
fallback when the carrier's own label isn't available (no API key, or carrier
without label support). reportlab is imported lazily so the dependency is only
needed when a label is actually generated.
"""
import io
from typing import Optional


def generate_label_pdf(
    *,
    tracking_number: str,
    carrier: str,
    order_number: str,
    sender_name: str,
    recipient_name: str,
    recipient_phone: str,
    recipient_address: str,
    weight_g: int,
    items_summary: str = "",
) -> bytes:
    """Render an A6 shipping label and return the PDF bytes."""
    from reportlab.lib.pagesizes import A6
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.graphics.barcode import code128
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.utils import simpleSplit

    buffer = io.BytesIO()
    width, height = A6  # 105 x 148 mm
    c = canvas.Canvas(buffer, pagesize=A6)

    margin = 8 * mm
    y = height - margin

    # Header: carrier + order
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin, y - 4 * mm, carrier.upper())
    c.setFont("Helvetica", 9)
    c.drawRightString(width - margin, y - 4 * mm, f"Заказ {order_number}")
    y -= 9 * mm
    c.line(margin, y, width - margin, y)
    y -= 6 * mm

    # Recipient block
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin, y, "ПОЛУЧАТЕЛЬ")
    y -= 5 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, recipient_name[:40])
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    c.drawString(margin, y, recipient_phone[:30])
    y -= 5 * mm
    for line in simpleSplit(recipient_address, "Helvetica", 9, width - 2 * margin):
        c.drawString(margin, y, line)
        y -= 4.5 * mm
    y -= 2 * mm

    # Sender + parcel
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin, y, "ОТПРАВИТЕЛЬ")
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    c.drawString(margin, y, sender_name[:40])
    y -= 5 * mm
    c.drawString(margin, y, f"Вес: {weight_g} г")
    if items_summary:
        y -= 4.5 * mm
        for line in simpleSplit(f"Состав: {items_summary}", "Helvetica", 8, width - 2 * margin)[:3]:
            c.drawString(margin, y, line)
            y -= 4 * mm

    # Barcode of the tracking number at the bottom
    barcode = code128.Code128(tracking_number, barHeight=16 * mm, barWidth=0.45 * mm)
    bc_width = barcode.width
    bc_x = (width - bc_width) / 2
    barcode.drawOn(c, bc_x, 14 * mm)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, 8 * mm, tracking_number)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

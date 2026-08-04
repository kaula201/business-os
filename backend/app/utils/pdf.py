"""PDF generation utilities for Business OS invoices."""
import io
import os
from datetime import date, datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Georgian text requires an embedded Unicode font. Never silently fall back to
# Helvetica: missing glyphs render as black squares in generated invoices.
FONT_NAME = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
_font_registered = False
for regular_path, bold_path in [
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ),
]:
    if os.path.exists(regular_path) and os.path.exists(bold_path):
        pdfmetrics.registerFont(TTFont(FONT_NAME, regular_path))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, bold_path))
        _font_registered = True
        break

if not _font_registered:
    raise RuntimeError("Georgian invoice font is missing; install fonts-dejavu-core")


def generate_invoice_pdf(
    invoice_number: str,
    order_number: str,
    company_name: str,
    company_id_code: str,
    company_address: str,
    company_phone: str,
    client_name: str,
    client_id_code: str,
    client_address: str,
    items: list[dict],
    subtotal: float,
    vat_amount: float,
    total: float,
    created_at: date | datetime,
    due_date: date | datetime | None = None,
) -> bytes:
    """Generate a Georgian-format invoice PDF and return bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm,
        leftMargin=2*cm, rightMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle("Normal", fontName=FONT_NAME, fontSize=10, leading=14)
    style_bold = ParagraphStyle("Bold", fontName=FONT_BOLD, fontSize=10, leading=14)
    style_title = ParagraphStyle("Title", fontName=FONT_BOLD, fontSize=18, leading=24)
    style_small = ParagraphStyle("Small", fontName=FONT_NAME, fontSize=8, leading=10)
    style_h2 = ParagraphStyle("H2", fontName=FONT_BOLD, fontSize=12, leading=16)

    elements = []

    # === Header ===
    header_data = [
        [Paragraph(f"<b>ინვოისი</b>", style_title),
         Paragraph(f"<b>№ {invoice_number}</b>", ParagraphStyle("Right", parent=style_bold, alignment=2))],
        [Paragraph(f"თარიღი: {created_at.strftime('%d.%m.%Y')}", style_normal),
         Paragraph(f"შეკვეთა: {order_number}", ParagraphStyle("Right", parent=style_normal, alignment=2))],
        [Paragraph(f"გადახდის ვადა: {due_date.strftime('%d.%m.%Y') if due_date else '—'}", style_normal), ""],
    ]
    t = Table(header_data, colWidths=[doc.width / 2, doc.width / 2])
    t.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2563eb")))
    elements.append(Spacer(1, 20))

    # === Seller (Company) ===
    elements.append(Paragraph("გამყიდველი:", style_h2))
    elements.append(Spacer(1, 4))
    seller_data = [
        [Paragraph(f"<b>{company_name}</b>", style_bold), ""],
        [Paragraph(f"საიდ. კოდი: {company_id_code}", style_normal), ""],
        [Paragraph(f"მისამართი: {company_address}", style_normal), ""],
        [Paragraph(f"ტელ: {company_phone}", style_normal), ""],
    ]
    t = Table(seller_data, colWidths=[doc.width * 0.4, doc.width * 0.6])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(t)
    elements.append(Spacer(1, 12))

    # === Buyer (Client) ===
    elements.append(Paragraph("მყიდველი:", style_h2))
    elements.append(Spacer(1, 4))
    buyer_data = [
        [Paragraph(f"<b>{client_name}</b>", style_bold), ""],
        [Paragraph(f"საიდ. კოდი: {client_id_code}", style_normal), ""],
        [Paragraph(f"მისამართი: {client_address}", style_normal), ""],
    ]
    t = Table(buyer_data, colWidths=[doc.width * 0.4, doc.width * 0.6])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(t)
    elements.append(Spacer(1, 20))

    # === Items Table ===
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elements.append(Spacer(1, 8))

    table_header = [
        ["#", "დასახელება", "რაოდ.", "ფასი (₾)", "ფასდ. %", "დღგ %", "ჯამი (₾)"]
    ]
    col_widths = [0.5*cm, None, 1.5*cm, 2*cm, 1.5*cm, 1.2*cm, 2*cm]

    table_data = [table_header[0]]

    for i, item in enumerate(items, 1):
        table_data.append([
            str(i),
            item.get("product_name", ""),
            f"{item.get('quantity', 0):.2f}",
            f"{item.get('unit_price', 0):.2f}",
            f"{item.get('discount_percent', 0):.0f}%",
            f"{item.get('vat_rate', 0):.0f}%",
            f"{item.get('total', 0):.2f}",
        ])

    # Derive the VAT label from the actual item rates (never hardcode 18%).
    vat_rates = {float(item.get("vat_rate", 0)) for item in items}
    if not items or vat_rates == {0}:
        vat_label = "დღგ:"
    elif len(vat_rates) == 1:
        vat_label = f"დღგ ({vat_rates.pop():.0f}%):"
    else:
        vat_label = "დღგ (პოზიციების მიხედვით):"

    table_data.append(["", "", "", "", "", "ქვე-ჯამი:", f"{subtotal:.2f}"])
    table_data.append(["", "", "", "", "", vat_label, f"{vat_amount:.2f}"])
    table_data.append(["", "", "", "", "", "სულ:", f"{total:.2f}"])

    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -4), 0.5, colors.grey),
        ("LINEBELOW", (0, -3), (-1, -3), 0.5, colors.grey),
        ("LINEBELOW", (0, -1), (-1, -1), 1, colors.HexColor("#2563eb")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eff6ff")),
        ("FONTNAME", (0, -1), (-1, -1), FONT_BOLD),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 30))

    # === Footer ===
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "გმადლობთ თანამშრომლობისთვის! | ფასები მოცემულია ლარში (₾)",
        style_small
    ))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
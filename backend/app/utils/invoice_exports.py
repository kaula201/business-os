"""Word and Excel exports for immutable issued customer invoices."""

import io
from decimal import Decimal

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def _set_cell_shading(cell, color: str) -> None:
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), color)
    cell._tc.get_or_add_tcPr().append(shading)


def generate_invoice_docx(invoice) -> bytes:
    document = Document()
    normal = document.styles["Normal"]
    normal.font.name = "DejaVu Sans"
    normal.font.size = Pt(10)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(f"ინვოისი № {invoice.invoice_number}")
    run.bold = True
    run.font.size = Pt(18)

    details = document.add_table(rows=3, cols=2)
    details.style = "Table Grid"
    details.cell(0, 0).text = f"თარიღი: {invoice.invoice_date:%d.%m.%Y}"
    details.cell(0, 1).text = f"შეკვეთა: {invoice.order_number}"
    details.cell(1, 0).text = f"გადახდის ვადა: {invoice.due_date:%d.%m.%Y}"
    details.cell(1, 1).text = f"ვალუტა: {invoice.currency}"
    details.cell(2, 0).text = f"გამყიდველი: {invoice.seller_name}\nსაიდ. კოდი: {invoice.seller_identification_code}\n{invoice.seller_address}"
    details.cell(2, 1).text = f"მყიდველი: {invoice.client_name}\nსაიდ. კოდი: {invoice.client_identification_code}\n{invoice.client_address}"

    document.add_paragraph()
    table = document.add_table(rows=1, cols=8)
    table.style = "Table Grid"
    headers = ["#", "დასახელება", "რაოდენობა", "ერთ. ფასი", "ფასდ. %", "დღგ %", "ქვე-ჯამი", "სულ"]
    for index, label in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = label
        _set_cell_shading(cell, "2563EB")
        for paragraph in cell.paragraphs:
            for text_run in paragraph.runs:
                text_run.font.color.rgb = None
                text_run.bold = True

    for line in invoice.items:
        cells = table.add_row().cells
        values = [
            line.line_number,
            line.product_name,
            f"{Decimal(line.quantity):.3f}",
            f"{Decimal(line.unit_price):.2f}",
            f"{Decimal(line.discount_percent):.2f}",
            f"{Decimal(line.vat_rate):.2f}",
            f"{Decimal(line.line_subtotal):.2f}",
            f"{Decimal(line.line_total):.2f}",
        ]
        for index, value in enumerate(values):
            cells[index].text = str(value)

    totals = document.add_table(rows=3, cols=2)
    totals.alignment = 2
    totals_data = [
        ("ქვე-ჯამი", invoice.subtotal),
        ("დღგ", invoice.vat_amount),
        ("სულ", invoice.total),
    ]
    for row, (label, value) in zip(totals.rows, totals_data):
        row.cells[0].text = label
        row.cells[1].text = f"{Decimal(value):.2f} {invoice.currency}"
        if label == "სულ":
            for cell in row.cells:
                _set_cell_shading(cell, "DBEAFE")
                for paragraph in cell.paragraphs:
                    for text_run in paragraph.runs:
                        text_run.bold = True

    if invoice.notes:
        document.add_paragraph(f"შენიშვნა: {invoice.notes}")

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def generate_invoice_xlsx(invoice) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "ინვოისი"
    sheet.sheet_view.showGridLines = False
    sheet.merge_cells("A1:H1")
    sheet["A1"] = f"ინვოისი № {invoice.invoice_number}"
    sheet["A1"].font = Font(name="Arial", size=18, bold=True, color="FFFFFF")
    sheet["A1"].fill = PatternFill("solid", fgColor="2563EB")
    sheet["A1"].alignment = Alignment(horizontal="center")
    sheet.row_dimensions[1].height = 30

    metadata = [
        ("თარიღი", invoice.invoice_date), ("შეკვეთა", invoice.order_number),
        ("გადახდის ვადა", invoice.due_date), ("ვალუტა", invoice.currency),
        ("გამყიდველი", invoice.seller_name), ("მყიდველი", invoice.client_name),
        ("გამყიდველის საიდ. კოდი", invoice.seller_identification_code),
        ("მყიდველის საიდ. კოდი", invoice.client_identification_code),
    ]
    for index, (label, value) in enumerate(metadata, start=3):
        column = 1 if index <= 6 else 5
        row = index if index <= 6 else index - 4
        sheet.cell(row, column, label).font = Font(name="Arial", bold=True)
        sheet.cell(row, column + 1, value).font = Font(name="Arial")

    header_row = 8
    headers = ["#", "დასახელება", "რაოდენობა", "ერთ. ფასი", "ფასდ. %", "დღგ %", "ქვე-ჯამი", "სულ"]
    thin = Side(style="thin", color="CBD5E1")
    for column, label in enumerate(headers, start=1):
        cell = sheet.cell(header_row, column, label)
        cell.font = Font(name="Arial", bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2563EB")
        cell.alignment = Alignment(horizontal="center")
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    first_line = header_row + 1
    for offset, line in enumerate(invoice.items):
        row = first_line + offset
        sheet.cell(row, 1, line.line_number)
        sheet.cell(row, 2, line.product_name)
        sheet.cell(row, 3, float(line.quantity))
        sheet.cell(row, 4, float(line.unit_price))
        sheet.cell(row, 5, float(line.discount_percent))
        sheet.cell(row, 6, float(line.vat_rate))
        sheet.cell(row, 7, f"=ROUND(C{row}*D{row}*(1-E{row}/100),2)")
        sheet.cell(row, 8, f"=ROUND(G{row}*(1+F{row}/100),2)")
        for column in range(1, 9):
            cell = sheet.cell(row, column)
            cell.font = Font(name="Arial")
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        for column in range(3, 9):
            sheet.cell(row, column).number_format = '#,##0.00;[Red](#,##0.00);-'

    last_line = first_line + len(invoice.items) - 1
    total_row = last_line + 2
    sheet.cell(total_row, 7, "ქვე-ჯამი").font = Font(name="Arial", bold=True)
    sheet.cell(total_row, 8, f"=SUM(G{first_line}:G{last_line})")
    sheet.cell(total_row + 1, 7, "დღგ").font = Font(name="Arial", bold=True)
    sheet.cell(total_row + 1, 8, f"=ROUND(SUMPRODUCT(G{first_line}:G{last_line},F{first_line}:F{last_line}/100),2)")
    sheet.cell(total_row + 2, 7, "სულ").font = Font(name="Arial", bold=True)
    sheet.cell(total_row + 2, 8, f"=SUM(H{first_line}:H{last_line})")
    for row in range(total_row, total_row + 3):
        sheet.cell(row, 8).number_format = '#,##0.00;[Red](#,##0.00);-'
    for column in (7, 8):
        sheet.cell(total_row + 2, column).fill = PatternFill("solid", fgColor="DBEAFE")
        sheet.cell(total_row + 2, column).font = Font(name="Arial", bold=True)

    if invoice.notes:
        sheet.cell(total_row + 4, 1, "შენიშვნა")
        sheet.cell(total_row + 4, 2, invoice.notes)
    widths = [6, 34, 14, 14, 12, 12, 16, 16]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = f"A{first_line}"
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcMode = "auto"

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()

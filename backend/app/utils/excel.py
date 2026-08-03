"""Excel export utilities for Business OS."""
import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# Colors
HEADER_FILL = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
ROW_FONT = Font(name="Calibri", size=10)
TITLE_FONT = Font(name="Calibri", bold=True, size=14)

THIN_BORDER = Border(
    left=Side(style='thin', color='D1D5DB'),
    right=Side(style='thin', color='D1D5DB'),
    top=Side(style='thin', color='D1D5DB'),
    bottom=Side(style='thin', color='D1D5DB'),
)


def _style_header(ws, cols: int):
    """Style the header row."""
    for col in range(1, cols + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = THIN_BORDER


def _style_data(ws, start_row: int, end_row: int, cols: int):
    """Style data rows."""
    for row in range(start_row, end_row + 1):
        for col in range(1, cols + 1):
            cell = ws.cell(row=row, column=col)
            cell.font = ROW_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical='center', wrap_text=False)


def _auto_width(ws, cols: int, max_width: int = 40):
    """Auto-adjust column widths."""
    for col in range(1, cols + 1):
        max_len = 0
        letter = get_column_letter(col)
        for row in ws.iter_rows(min_col=col, max_col=col, values_only=False):
            for cell in row:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[letter].width = min(max_len + 3, max_width)


def export_clients(clients: list[dict]) -> bytes:
    """Export clients to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "კლიენტები"

    # Title
    ws.merge_cells('A1:G1')
    ws['A1'] = "კლიენტების სია"
    ws['A1'].font = TITLE_FONT
    ws['A1'].alignment = Alignment(horizontal='center')

    # Header (row 3)
    headers = ["#", "სახელი", "ტიპი", "საიდ. კოდი", "სტატუსი", "ტელეფონი", "ელფოსტა", "შექმნის თარიღი"]
    for col, h in enumerate(headers, 1):
        ws.cell(row=3, column=col, value=h)
    _style_header(ws, len(headers))

    # Data
    for i, c in enumerate(clients, 1):
        row = i + 3
        ws.cell(row=row, column=1, value=i)
        ws.cell(row=row, column=2, value=c.get("name", ""))
        ws.cell(row=row, column=3, value="იურ. პირი" if c.get("client_type") == "legal" else "ფიზ. პირი")
        ws.cell(row=row, column=4, value=c.get("identification_code", ""))
        status = c.get("status", "")
        status_map = {"active": "აქტიური", "potential": "პოტენციური", "inactive": "არააქტიური"}
        ws.cell(row=row, column=5, value=status_map.get(status, status))
        ws.cell(row=row, column=6, value=c.get("phone", ""))
        ws.cell(row=row, column=7, value=c.get("email", ""))
        ws.cell(row=row, column=8, value=str(c.get("created_at", ""))[:10])

    _style_data(ws, 4, len(clients) + 3, len(headers))
    _auto_width(ws, len(headers))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def export_products(products: list[dict]) -> bytes:
    """Export products/inventory to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "საწყობი"

    ws.merge_cells('A1:I1')
    ws['A1'] = "პროდუქტების სია"
    ws['A1'].font = TITLE_FONT
    ws['A1'].alignment = Alignment(horizontal='center')

    headers = ["#", "SKU", "დასახელება", "კატეგორია", "ერთეული",
               "მიმდ. ნაშთი", "მინ. ნაშთი", "გასაყ. ფასი (₾)", "შეძ. ფასი (₾)"]
    for col, h in enumerate(headers, 1):
        ws.cell(row=3, column=col, value=h)
    _style_header(ws, len(headers))

    for i, p in enumerate(products, 1):
        row = i + 3
        ws.cell(row=row, column=1, value=i)
        ws.cell(row=row, column=2, value=p.get("sku", ""))
        ws.cell(row=row, column=3, value=p.get("name", ""))
        ws.cell(row=row, column=4, value=p.get("category_name", ""))
        ws.cell(row=row, column=5, value=p.get("unit", ""))
        ws.cell(row=row, column=6, value=p.get("current_stock", 0))
        ws.cell(row=row, column=7, value=p.get("min_stock", 0))
        ws.cell(row=row, column=8, value=p.get("sale_price", 0))
        ws.cell(row=row, column=9, value=p.get("purchase_price", 0) or "—")

    _style_data(ws, 4, len(products) + 3, len(headers))
    _auto_width(ws, len(headers))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def export_orders(orders: list[dict]) -> bytes:
    """Export orders to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "შეკვეთები"

    ws.merge_cells('A1:H1')
    ws['A1'] = "შეკვეთების სია"
    ws['A1'].font = TITLE_FONT
    ws['A1'].alignment = Alignment(horizontal='center')

    status_map = {
        "draft": "ახალი", "confirmed": "დამტკიცებული", "preparing": "მზადდება",
        "shipping": "მიწოდებაში", "completed": "დასრულებული", "cancelled": "გაუქმებული"
    }

    headers = ["#", "შეკვეთა", "კლიენტი", "სტატუსი", "დღგ", "ჯამი (₾)", "შექმნის თარიღი", "შენიშვნა"]
    for col, h in enumerate(headers, 1):
        ws.cell(row=3, column=col, value=h)
    _style_header(ws, len(headers))

    for i, o in enumerate(orders, 1):
        row = i + 3
        ws.cell(row=row, column=1, value=i)
        ws.cell(row=row, column=2, value=o.get("order_number", ""))
        ws.cell(row=row, column=3, value=o.get("client_name", ""))
        ws.cell(row=row, column=4, value=status_map.get(o.get("status", ""), o.get("status", "")))
        ws.cell(row=row, column=5, value=o.get("vat_amount", 0))
        ws.cell(row=row, column=6, value=o.get("total", 0))
        ws.cell(row=row, column=7, value=str(o.get("created_at", ""))[:10])
        ws.cell(row=row, column=8, value=o.get("notes", ""))

    _style_data(ws, 4, len(orders) + 3, len(headers))
    _auto_width(ws, len(headers))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def export_tasks(tasks: list[dict]) -> bytes:
    """Export tasks to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "დავალებები"

    ws.merge_cells('A1:G1')
    ws['A1'] = "დავალებების სია"
    ws['A1'].font = TITLE_FONT
    ws['A1'].alignment = Alignment(horizontal='center')

    status_map = {"todo": "საჭიროებს", "in_progress": "პროცესში", "done": "დასრულებული", "cancelled": "გაუქმებული"}
    priority_map = {"low": "დაბალი", "medium": "საშუალო", "high": "მაღალი"}

    headers = ["#", "სათაური", "პრიორიტეტი", "სტატუსი", "პასუხისმგებელი", "ვადა", "შექმნის თარიღი"]
    for col, h in enumerate(headers, 1):
        ws.cell(row=3, column=col, value=h)
    _style_header(ws, len(headers))

    for i, t in enumerate(tasks, 1):
        row = i + 3
        ws.cell(row=row, column=1, value=i)
        ws.cell(row=row, column=2, value=t.get("title", ""))
        ws.cell(row=row, column=3, value=priority_map.get(t.get("priority", ""), t.get("priority", "")))
        ws.cell(row=row, column=4, value=status_map.get(t.get("status", ""), t.get("status", "")))
        ws.cell(row=row, column=5, value=t.get("assigned_to_name", ""))
        ws.cell(row=row, column=6, value=str(t.get("due_date", ""))[:10] if t.get("due_date") else "—")
        ws.cell(row=row, column=7, value=str(t.get("created_at", ""))[:10])

    _style_data(ws, 4, len(tasks) + 3, len(headers))
    _auto_width(ws, len(headers))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
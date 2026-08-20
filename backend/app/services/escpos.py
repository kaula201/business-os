"""ESC/POS receipt generation — thermal printer + cash drawer commands.

Generates the raw ESC/POS byte stream for a POS receipt (Odoo IoT-box style).
The stream can be sent to a network printer (port 9100) or a USB device.
"""

# ESC/POS control bytes
ESC = b"\x1b"
GS = b"\x1d"
INIT = ESC + b"@"                      # initialize printer
CUT = GS + b"V" + b"\x41" + b"\x03"    # paper cut
DRAWER = ESC + b"p" + b"\x00" + b"\x19" + b"\xfa"  # open cash drawer (pin 2)
BOLD_ON = ESC + b"E" + b"\x01"
BOLD_OFF = ESC + b"E" + b"\x00"
ALIGN_CENTER = ESC + b"a" + b"\x01"
ALIGN_LEFT = ESC + b"a" + b"\x00"
SIZE_DOUBLE = GS + b"!" + b"\x11"      # double height+width
SIZE_NORMAL = GS + b"!" + b"\x00"


def _line(text: str, align: bytes = ALIGN_LEFT, bold: bool = False, size: bytes = SIZE_NORMAL) -> bytes:
    return align + size + (BOLD_ON if bold else BOLD_OFF) + text.encode("cp437", errors="replace") + b"\n"


def build_receipt(order: dict, company_name: str = "Business OS") -> bytes:
    """Build the ESC/POS byte stream for a completed order."""
    out = bytearray()
    out += INIT
    out += _line(company_name, ALIGN_CENTER, bold=True, size=SIZE_DOUBLE)
    out += _line("--------------------------------", ALIGN_CENTER)
    out += _line(f"ჩეკი: {order.get('order_number', '')}", ALIGN_CENTER, bold=True)
    out += _line(f"თარიღი: {order.get('created_at', '')[:16]}", ALIGN_CENTER)
    out += _line("--------------------------------", ALIGN_CENTER)
    for it in order.get("items", []):
        name = it.get("product_name", "")
        qty = it.get("quantity", 1)
        total = it.get("line_total", 0)
        out += _line(f"{name}")
        out += _line(f"  {qty} x {total:.2f} GEL")
    out += _line("--------------------------------", ALIGN_CENTER)
    out += _line(f"ქვეჯამი: {order.get('subtotal', 0):.2f}", bold=True)
    if order.get("discount_amount"):
        out += _line(f"ფასდაკლება: -{order['discount_amount']:.2f}")
    if order.get("tip_amount"):
        out += _line(f"ჩაი: {order['tip_amount']:.2f}")
    out += _line(f"VAT 18%: {order.get('vat_amount', 0):.2f}")
    out += _line(f"სულ: {order.get('total', 0):.2f} GEL", bold=True, size=SIZE_DOUBLE)
    out += _line("")
    out += _line("გმადლობთ!", ALIGN_CENTER)
    out += _line("")
    out += DRAWER
    out += CUT
    return bytes(out)


def open_cash_drawer() -> bytes:
    """Just the cash drawer kick command."""
    return INIT + DRAWER

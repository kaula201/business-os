"""VAT return and registers from issued invoices."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.invoice import Invoice
from tests.test_customer_invoicing import create_invoice_order
from tests.test_supplier_payables import create_supplier_invoice, setup_received_purchase

pytestmark = pytest.mark.asyncio

AUG_START = date(2026, 8, 1)
AUG_END = date(2026, 8, 31)


async def test_vat_return_computes_net_payable(client, auth_headers, test_company, db_session):
    # Sales: 1000 + 180 VAT (issued invoice dated 2026-08)
    order, _, _ = await create_invoice_order(client, auth_headers, test_company, db_session, "VAT-A")
    inv = (await db_session.execute(select(Invoice).where(Invoice.order_id == order["id"]))).scalar_one()
    inv.status = "issued"
    inv.invoice_date = date(2026, 8, 15)
    inv.due_date = date(2026, 8, 25)
    inv.subtotal = Decimal("1000")
    inv.vat_amount = Decimal("180")
    inv.total = Decimal("1180")
    await db_session.commit()

    # Purchases: 600 + 108 VAT (supplier invoice dated 2026-08)
    supplier, po = await setup_received_purchase(client, auth_headers, test_company, db_session, "VAT-A", quantity=10, unit_price=60)
    await create_supplier_invoice(
        client, auth_headers, supplier, po, "VAT-A",
        quantity=10, unit_price=60, due_date=date(2026, 9, 10),
    )
    # the helper uses invoice_date = today; force it into August 2026
    from app.models.purchase import SupplierInvoice
    si = (await db_session.execute(
        select(SupplierInvoice).where(SupplierInvoice.supplier_invoice_number == "VENDOR-VAT-A")
    )).scalar_one()
    si.invoice_date = date(2026, 8, 10)
    si.subtotal = Decimal("600")
    si.vat_amount = Decimal("108")
    si.total = Decimal("708")
    await db_session.commit()

    resp = await client.get("/api/v1/tax-reports/vat", params={"year": 2026, "month": 8}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d["period"] == "2026-08"
    assert d["sales"]["invoice_count"] == 1
    assert d["sales"]["subtotal"] == 1000.0
    assert d["sales"]["vat"] == 180.0
    assert d["purchases"]["invoice_count"] == 1
    assert d["purchases"]["vat"] == 108.0
    assert d["net_vat_payable"] == 72.0

    # September must be empty
    resp2 = await client.get("/api/v1/tax-reports/vat", params={"year": 2026, "month": 9}, headers=auth_headers)
    assert resp2.status_code == 200, resp2.text
    d2 = resp2.json()["data"]
    assert d2["sales"]["invoice_count"] == 0
    assert d2["purchases"]["invoice_count"] == 0
    assert d2["net_vat_payable"] == 0.0


async def test_vat_registers_list_rows(client, auth_headers, test_company, db_session):
    # one sales invoice + one supplier invoice in August 2026
    order, _, _ = await create_invoice_order(client, auth_headers, test_company, db_session, "VAT-B")
    inv = (await db_session.execute(select(Invoice).where(Invoice.order_id == order["id"]))).scalar_one()
    inv.status = "issued"
    inv.invoice_date = date(2026, 8, 16)
    inv.subtotal = Decimal("500")
    inv.vat_amount = Decimal("90")
    inv.total = Decimal("590")
    await db_session.commit()

    supplier, purchase = await create_purchases(client, auth_headers, test_company, db_session, "VAT-B")
    await create_supplier_invoice(
        client, auth_headers, supplier, purchase, "VAT-B",
        quantity=5, unit_price=100, due_date=date(2026, 9, 5),
    )
    from app.models.purchase import SupplierInvoice
    si = (await db_session.execute(
        select(SupplierInvoice).where(SupplierInvoice.supplier_invoice_number == "VENDOR-VAT-B")
    )).scalar_one()
    si.invoice_date = date(2026, 8, 11)
    si.subtotal = Decimal("500")
    si.vat_amount = Decimal("90")
    si.total = Decimal("590")
    await db_session.commit()

    sales = await client.get(
        "/api/v1/tax-reports/vat/register/sales",
        params={"date_from": "2026-08-01", "date_to": "2026-08-31"},
        headers=auth_headers,
    )
    assert sales.status_code == 200, sales.text
    rows = sales.json()["data"]
    assert len(rows) == 1
    assert rows[0]["vat"] == 90.0
    assert rows[0]["invoice_number"] == inv.invoice_number

    purchases = await client.get(
        "/api/v1/tax-reports/vat/register/purchases",
        params={"date_from": "2026-08-01", "date_to": "2026-08-31"},
        headers=auth_headers,
    )
    assert purchases.status_code == 200, purchases.text
    rows_p = purchases.json()["data"]
    assert len(rows_p) == 1
    assert rows_p[0]["supplier_invoice_number"] == "VENDOR-VAT-B"
    assert rows_p[0]["vat"] == 90.0


async def create_purchases(client, auth_headers, test_company, db_session, suffix: str):
    """Small wrapper matching the supplier-payables flow."""
    from tests.test_supplier_payables import setup_received_purchase
    supplier, po = await setup_received_purchase(
        client, auth_headers, test_company, db_session, suffix,
        quantity=5, unit_price=100,
    )
    return supplier, po


# re-export for readability
create_purchase = create_purchases

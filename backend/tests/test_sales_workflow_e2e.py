"""End-to-end sales workflow: Lead → Client → Order → Invoice → Payment → GL → Dashboard.

Verifies the canonical revenue semantics end-to-end:
- revenue is recognized ONLY from issued invoices;
- GL posting stays balanced at every step;
- Dashboard aggregates match the underlying ledger.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.gl import JournalEntry, JournalEntryLine
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.product import Product
from app.models.receivable import CustomerReceivable
from app.models.warehouse import InventoryBalance, Warehouse


async def create_sales_context(client, auth_headers, test_company, db_session, suffix: str):
    """Lead → qualified → convert → Client in the registry."""
    lead = await client.post(
        "/api/v1/crm/leads",
        headers=auth_headers,
        json={
            "company_name": f"E2E Customer {suffix}",
            "contact_name": "E2E Contact",
            "email": f"e2e{suffix}@example.ge",
            "phone": "+995500000000",
            "source": "campaign",
            "estimated_value": 20000,
        },
    )
    assert lead.status_code == 201, lead.text
    lead_id = lead.json()["data"]["id"]

    qualified = await client.patch(
        f"/api/v1/crm/leads/{lead_id}",
        headers=auth_headers,
        json={"status": "qualified"},
    )
    assert qualified.status_code == 200, qualified.text

    converted = await client.post(
        f"/api/v1/crm/leads/{lead_id}/convert",
        headers=auth_headers,
        json={
            "client_type": "legal",
            "identification_code": f"E2E-{suffix}-001",
            "is_vat_payer": False,
            "address": "თბილისი, E2E ქუჩა 1",
        },
    )
    assert converted.status_code == 201, converted.text
    client_id = converted.json()["data"]["client"]["id"]

    product = Product(
        company_id=test_company.id,
        sku=f"E2E-SKU-{suffix}",
        name=f"E2E Product {suffix}",
        sale_price=Decimal("250.00"),
        current_stock=100,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code=f"E2E-WH-{suffix}",
        name=f"E2E Warehouse {suffix}",
        is_default=True,
        is_active=True,
    )
    db_session.add_all([product, warehouse])
    await db_session.flush()
    db_session.add(
        InventoryBalance(
            company_id=test_company.id,
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=Decimal("100"),
        )
    )
    await db_session.commit()
    await db_session.refresh(product)
    return client_id, product, warehouse


@pytest.mark.asyncio
async def test_full_sales_workflow_revenue_and_gl_stay_consistent(
    client, auth_headers, test_company, db_session
):
    client_id, product, warehouse = await create_sales_context(
        client, auth_headers, test_company, db_session, "FLOW"
    )

    # ── 1. Order (draft → confirmed) ──────────────────────────────────────
    order_res = await client.post(
        "/api/v1/orders/",
        json={
            "client_id": client_id,
            "warehouse_id": str(warehouse.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "quantity": 4,
                    "unit_price": 250,
                    "discount_percent": 0,
                }
            ],
            "is_vat_payer": False,
        },
        headers=auth_headers,
    )
    assert order_res.status_code == 200, order_res.text
    order_id = order_res.json()["data"]["id"]
    assert order_res.json()["data"]["total"] == 1000

    confirmed = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "confirmed"},
        headers=auth_headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    # ── 2. Invoice generation → issued, receivable + GL entry ─────────────
    invoice_res = await client.post(
        "/api/v1/invoices/generate",
        json={
            "order_id": order_id,
            "idempotency_key": "e2e-flow-invoice",
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
        },
        headers=auth_headers,
    )
    assert invoice_res.status_code == 200, invoice_res.text
    invoice = invoice_res.json()["data"]
    assert invoice["status"] == "issued"
    assert invoice["total"] == 1000

    receivable = (
        await db_session.execute(
            select(CustomerReceivable).where(CustomerReceivable.invoice_id == invoice["id"])
        )
    ).scalar_one()
    assert receivable.outstanding_amount == Decimal("1000")

    # ── 3. Payment → receivable closed, payment GL entry ──────────────────
    payment_res = await client.post(
        f"/api/v1/customer-receivables/{receivable.id}/payments",
        json={
            "idempotency_key": "e2e-flow-payment",
            "amount": 1000,
            "payment_date": date.today().isoformat(),
            "payment_method": "bank_transfer",
            "reference": "E2E-PAY-001",
        },
        headers=auth_headers,
    )
    assert payment_res.status_code == 200, payment_res.text
    payment_result = payment_res.json()["data"]
    assert payment_result["receivable"]["outstanding_amount"] == 0
    assert payment_result["receivable"]["status"] == "paid"

    # ── 4. GL: every entry balanced, entries exist for invoice + payment ──
    entries = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.company_id == test_company.id)
        )
    ).scalars().all()
    assert len(entries) >= 2

    for entry in entries:
        lines = (
            await db_session.execute(
                select(JournalEntryLine).where(
                    JournalEntryLine.journal_entry_id == entry.id
                )
            )
        ).scalars().all()
        debit = sum(Decimal(line.debit_amount) for line in lines)
        credit = sum(Decimal(line.credit_amount) for line in lines)
        assert debit == credit, f"Unbalanced GL entry {entry.entry_number}"

    # ── 5. Dashboard: revenue = issued invoice total (1000) ───────────────
    dashboard_res = await client.get(
        "/api/v1/dashboard/summary?period=30d",
        headers=auth_headers,
    )
    assert dashboard_res.status_code == 200
    dashboard = dashboard_res.json()["data"]
    assert dashboard["total_revenue"] == 1000.0
    assert dashboard["kpi"]["total_revenue"] == 1000.0
    assert dashboard["invoiced_orders_count"] >= 1
    assert dashboard["total_orders_count"] >= 1


@pytest.mark.asyncio
async def test_workflow_blocks_invoice_for_cancelled_order(
    client, auth_headers, test_company, db_session
):
    """A cancelled order must not be invoiceable (sales integrity)."""
    client_id, product, warehouse = await create_sales_context(
        client, auth_headers, test_company, db_session, "CANCEL"
    )
    order_res = await client.post(
        "/api/v1/orders/",
        json={
            "client_id": client_id,
            "warehouse_id": str(warehouse.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "quantity": 1,
                    "unit_price": 100,
                    "discount_percent": 0,
                }
            ],
            "is_vat_payer": False,
        },
        headers=auth_headers,
    )
    assert order_res.status_code == 200, order_res.text
    order_id = order_res.json()["data"]["id"]

    cancelled = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=auth_headers,
    )
    assert cancelled.status_code == 200, cancelled.text

    invoice_res = await client.post(
        "/api/v1/invoices/generate",
        json={
            "order_id": order_id,
            "idempotency_key": "e2e-cancel-invoice",
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
        },
        headers=auth_headers,
    )
    assert invoice_res.status_code in (400, 409), invoice_res.text

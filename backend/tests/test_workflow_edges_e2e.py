"""E1 — Partial delivery/payment and returns/reversals, end-to-end.

Extends the E2E coverage with the lifecycle edges:
- partial goods receipt -> partially_received -> second receipt completes it;
- partial customer payment -> partially_paid -> full payment -> paid;
- customer credit note reduces outstanding; customer payment reversal
  restores it; both keep GL balanced;
- supplier credit note reduces payable; supplier payment reversal restores it.
"""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.gl import JournalEntry, JournalEntryLine
from app.models.invoice import Invoice
from app.models.product import Product
from app.models.receivable import CustomerReceivable
from app.models.warehouse import InventoryBalance, Warehouse


async def create_e1_sales_context(client, auth_headers, test_company, db_session, suffix: str):
    product = Product(
        company_id=test_company.id,
        sku=f"E1-SALE-{suffix}",
        name=f"E1 Sale Product {suffix}",
        sale_price=100,
        purchase_price=50,
        unit="ცალი",
        min_stock=0,
        current_stock=0,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code=f"E1-SALE-WH-{suffix}",
        name=f"E1 Sale Warehouse {suffix}",
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

    client_res = await client.post(
        "/api/v1/clients/",
        json={
            "name": f"E1 Client {suffix}",
            "client_type": "legal",
            "identification_code": f"{uuid4().int % 900000000 + 100000000}",
            "status": "active",
            "is_vat_payer": False,
        },
        headers=auth_headers,
    )
    assert client_res.status_code == 200, client_res.text
    return product, warehouse, client_res.json()["data"]


async def create_e1_purchase_context(client, auth_headers, test_company, db_session, suffix: str):
    product = Product(
        company_id=test_company.id,
        sku=f"E1-PUR-{suffix}",
        name=f"E1 Purchase Product {suffix}",
        sale_price=30,
        purchase_price=10,
        unit="ცალი",
        min_stock=0,
        current_stock=0,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code=f"E1-PUR-WH-{suffix}",
        name=f"E1 Purchase Warehouse {suffix}",
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
            quantity=Decimal("0"),
        )
    )
    await db_session.commit()
    await db_session.refresh(product)

    supplier_res = await client.post(
        "/api/v1/suppliers/",
        json={
            "code": f"E1-SUP-{suffix}",
            "name": f"E1 Supplier {suffix}",
            "identification_code": f"{uuid4().int % 900000000 + 100000000}",
            "is_vat_payer": True,
            "contact_name": "E1 Supplier Contact",
            "phone": "+995500000002",
            "email": f"e1{suffix}@supplier.ge",
            "payment_terms_days": 30,
        },
        headers=auth_headers,
    )
    assert supplier_res.status_code == 200, supplier_res.text
    return product, warehouse, supplier_res.json()["data"]


async def assert_all_gl_balanced(db_session, company_id):
    entries = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.company_id == company_id)
        )
    ).scalars().all()
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


@pytest.mark.asyncio
async def test_partial_goods_receipt_then_completion(
    client, auth_headers, test_company, db_session
):
    product, warehouse, supplier = await create_e1_purchase_context(
        client, auth_headers, test_company, db_session, "PARTIAL-RECV"
    )
    po_res = await client.post(
        "/api/v1/purchase-orders/",
        json={
            "supplier_id": supplier["id"],
            "warehouse_id": str(warehouse.id),
            "expected_delivery_date": (date.today() + timedelta(days=10)).isoformat(),
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 10,
                    "unit_price": 10,
                    "discount_percent": 0,
                    "vat_rate": 0,
                }
            ],
        },
        headers=auth_headers,
    )
    assert po_res.status_code == 200, po_res.text
    po = po_res.json()["data"]
    po_item_id = po["items"][0]["id"]

    approved = await client.patch(
        f"/api/v1/purchase-orders/{po['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text

    # Partial receipt: 4 of 10
    partial = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={
            "idempotency_key": "e1-partial-receipt-1",
            "items": [{"purchase_order_item_id": po_item_id, "quantity": 4}],
        },
        headers=auth_headers,
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["data"]["status"] == "posted"

    po_after = (
        await client.get(f"/api/v1/purchase-orders/{po['id']}", headers=auth_headers)
    ).json()["data"]
    assert po_after["status"] == "partially_received"
    assert po_after["items"][0]["received_quantity"] == 4

    await db_session.refresh(product)
    assert product.current_stock == 4

    # Second receipt completes: 6 more
    complete = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={
            "idempotency_key": "e1-partial-receipt-2",
            "items": [{"purchase_order_item_id": po_item_id, "quantity": 6}],
        },
        headers=auth_headers,
    )
    assert complete.status_code == 200, complete.text

    po_final = (
        await client.get(f"/api/v1/purchase-orders/{po['id']}", headers=auth_headers)
    ).json()["data"]
    assert po_final["status"] == "received"
    assert po_final["items"][0]["received_quantity"] == 10

    await db_session.refresh(product)
    assert product.current_stock == 10

    await assert_all_gl_balanced(db_session, test_company.id)


@pytest.mark.asyncio
async def test_partial_payment_then_full_payment_and_reversal(
    client, auth_headers, test_company, db_session
):
    product, warehouse, customer = await create_e1_sales_context(
        client, auth_headers, test_company, db_session, "PARTIAL-PAY"
    )
    order_res = await client.post(
        "/api/v1/orders/",
        json={
            "client_id": customer["id"],
            "warehouse_id": str(warehouse.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "quantity": 10,
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

    confirmed = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "confirmed"},
        headers=auth_headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    invoice_res = await client.post(
        "/api/v1/invoices/generate",
        json={
            "order_id": order_id,
            "idempotency_key": "e1-partial-pay-invoice",
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
        },
        headers=auth_headers,
    )
    assert invoice_res.status_code == 200, invoice_res.text
    assert invoice_res.json()["data"]["total"] == 1000

    receivable = (
        await db_session.execute(
            select(CustomerReceivable).where(
                CustomerReceivable.company_id == test_company.id
            )
        )
    ).scalars().one()
    assert receivable.outstanding_amount == Decimal("1000")

    # Partial payment: 400 of 1000
    partial = await client.post(
        f"/api/v1/customer-receivables/{receivable.id}/payments",
        json={
            "idempotency_key": "e1-partial-payment",
            "amount": 400,
            "payment_date": date.today().isoformat(),
            "payment_method": "bank_transfer",
            "reference": "E1-PARTIAL-PAY",
        },
        headers=auth_headers,
    )
    assert partial.status_code == 200, partial.text
    partial_result = partial.json()["data"]
    assert partial_result["receivable"]["status"] == "partially_paid"
    assert partial_result["receivable"]["outstanding_amount"] == 600
    payment = partial_result["payment"]

    # Full payment: 600 more
    full = await client.post(
        f"/api/v1/customer-receivables/{receivable.id}/payments",
        json={
            "idempotency_key": "e1-full-payment",
            "amount": 600,
            "payment_date": date.today().isoformat(),
            "payment_method": "bank_transfer",
            "reference": "E1-FULL-PAY",
        },
        headers=auth_headers,
    )
    assert full.status_code == 200, full.text
    assert full.json()["data"]["receivable"]["status"] == "paid"
    full_payment = full.json()["data"]["payment"]

    # Reversal of the FULL payment restores outstanding to 600
    reversal = await client.post(
        f"/api/v1/customer-payments/{full_payment['id']}/reversal",
        json={
            "idempotency_key": "e1-partial-pay-reversal",
            "reason": "კლიენტმა უარი თქვა მეორე ტრანშზე",
        },
        headers=auth_headers,
    )
    assert reversal.status_code == 200, reversal.text
    reversed_result = reversal.json()["data"]
    assert reversed_result["payment"]["status"] == "reversed"
    assert reversed_result["receivable"]["status"] == "partially_paid"
    assert reversed_result["receivable"]["outstanding_amount"] == 600

    await assert_all_gl_balanced(db_session, test_company.id)


@pytest.mark.asyncio
async def test_customer_credit_note_reduces_outstanding(
    client, auth_headers, test_company, db_session
):
    product, warehouse, customer = await create_e1_sales_context(
        client, auth_headers, test_company, db_session, "CREDIT"
    )
    order_res = await client.post(
        "/api/v1/orders/",
        json={
            "client_id": customer["id"],
            "warehouse_id": str(warehouse.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "quantity": 5,
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
    confirmed = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "confirmed"},
        headers=auth_headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    invoice_res = await client.post(
        "/api/v1/invoices/generate",
        json={
            "order_id": order_id,
            "idempotency_key": "e1-credit-invoice",
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
        },
        headers=auth_headers,
    )
    assert invoice_res.status_code == 200, invoice_res.text
    assert invoice_res.json()["data"]["total"] == 500

    receivable = (
        await db_session.execute(
            select(CustomerReceivable).where(
                CustomerReceivable.company_id == test_company.id
            )
        )
    ).scalars().one()

    credited = await client.post(
        f"/api/v1/customer-receivables/{receivable.id}/credit-notes",
        json={
            "idempotency_key": "e1-customer-credit",
            "credit_note_number": "E1-CN-001",
            "amount": 120,
            "credit_date": date.today().isoformat(),
            "reason": "ნაწილის დაბრუნება",
        },
        headers=auth_headers,
    )
    assert credited.status_code == 200, credited.text
    result = credited.json()["data"]
    assert result["receivable"]["credited_amount"] == 120
    assert result["receivable"]["outstanding_amount"] == 380

    await assert_all_gl_balanced(db_session, test_company.id)


@pytest.mark.asyncio
async def test_supplier_credit_note_and_payment_reversal_restore_payable(
    client, auth_headers, test_company, db_session
):
    product, warehouse, supplier = await create_e1_purchase_context(
        client, auth_headers, test_company, db_session, "SUP-REV"
    )
    po_res = await client.post(
        "/api/v1/purchase-orders/",
        json={
            "supplier_id": supplier["id"],
            "warehouse_id": str(warehouse.id),
            "expected_delivery_date": (date.today() + timedelta(days=10)).isoformat(),
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 5,
                    "unit_price": 10,
                    "discount_percent": 0,
                    "vat_rate": 18,
                }
            ],
        },
        headers=auth_headers,
    )
    assert po_res.status_code == 200, po_res.text
    po = po_res.json()["data"]
    po_item_id = po["items"][0]["id"]
    approved = await client.patch(
        f"/api/v1/purchase-orders/{po['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text
    receipt = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={
            "idempotency_key": "e1-sup-rev-receipt",
            "items": [{"purchase_order_item_id": po_item_id, "quantity": 5}],
        },
        headers=auth_headers,
    )
    assert receipt.status_code == 200, receipt.text

    invoice_res = await client.post(
        "/api/v1/supplier-invoices/",
        json={
            "supplier_id": supplier["id"],
            "purchase_order_id": po["id"],
            "supplier_invoice_number": f"E1-SUP-INV-{date.today().isoformat()}",
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=30)).isoformat(),
            "items": [
                {
                    "purchase_order_item_id": po_item_id,
                    "quantity": 5,
                    "unit_price": 10,
                    "discount_percent": 0,
                    "vat_rate": 18,
                }
            ],
        },
        headers=auth_headers,
    )
    assert invoice_res.status_code == 200, invoice_res.text
    invoice = invoice_res.json()["data"]
    assert invoice["total"] == 59

    approved_inv = await client.patch(
        f"/api/v1/supplier-invoices/{invoice['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved_inv.status_code == 200, approved_inv.text
    payable_id = approved_inv.json()["data"]["payable"]["id"]

    # Supplier credit note: 59 -> 29 outstanding
    credited = await client.post(
        f"/api/v1/supplier-payables/{payable_id}/credit-notes",
        json={
            "idempotency_key": "e1-supplier-credit",
            "supplier_credit_note_number": "E1-SUP-CN-001",
            "amount": 30,
            "credit_date": date.today().isoformat(),
            "reason": "დაბრუნებული საქონელი",
        },
        headers=auth_headers,
    )
    assert credited.status_code == 200, credited.text
    assert credited.json()["data"]["credited_amount"] == 30
    assert credited.json()["data"]["outstanding_amount"] == 29

    # Pay the remainder, then reverse the payment
    paid = await client.post(
        f"/api/v1/supplier-payables/{payable_id}/payments",
        json={
            "idempotency_key": "e1-sup-pay",
            "amount": 29,
            "payment_date": date.today().isoformat(),
            "payment_method": "bank_transfer",
            "reference": "E1-SUP-PAY",
        },
        headers=auth_headers,
    )
    assert paid.status_code == 200, paid.text
    payment = paid.json()["data"]["payments"][0]
    assert paid.json()["data"]["status"] == "paid"

    reversed_res = await client.post(
        f"/api/v1/supplier-payments/{payment['id']}/reversal",
        json={
            "idempotency_key": "e1-sup-pay-reversal",
            "reason": "გადახდა გაუქმდა",
        },
        headers=auth_headers,
    )
    assert reversed_res.status_code == 200, reversed_res.text
    restored = reversed_res.json()["data"]
    assert restored["status"] == "unpaid"
    assert restored["outstanding_amount"] == 29
    assert restored["paid_amount"] == 0

    await assert_all_gl_balanced(db_session, test_company.id)

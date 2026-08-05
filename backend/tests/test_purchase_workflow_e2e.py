"""End-to-end purchase workflow: Purchase Order → Receipt → Supplier Invoice →
Payable → Payment → GL.

Verifies the canonical procure-to-pay semantics:
- goods receipt increases stock and moves stock cost;
- supplier invoice creates a payable + balanced GL entry;
- payment closes the payable and creates another balanced GL entry;
- every GL entry stays balanced (debit == credit).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.gl import JournalEntry, JournalEntryLine
from app.models.product import Product
from app.models.warehouse import InventoryBalance, InventoryMovement, Warehouse


async def create_purchase_context(client, auth_headers, test_company, db_session, suffix: str):
    product = Product(
        company_id=test_company.id,
        sku=f"PUR-E2E-{suffix}",
        name=f"E2E Purchase Product {suffix}",
        sale_price=30,
        purchase_price=10,
        unit="ცალი",
        min_stock=1,
        current_stock=0,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code=f"E2E-PUR-{suffix}",
        name=f"E2E Purchase Warehouse {suffix}",
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
            "code": f"SUP-E2E-{suffix}",
            "name": f"E2E Supplier {suffix}",
            "identification_code": f"E2E-SUP-{suffix}",
            "is_vat_payer": True,
            "contact_name": "E2E Supplier Contact",
            "phone": "+995500000001",
            "email": f"e2e{suffix}@supplier.ge",
            "payment_terms_days": 30,
        },
        headers=auth_headers,
    )
    assert supplier_res.status_code == 200, supplier_res.text

    return product, warehouse, supplier_res.json()["data"]


@pytest.mark.asyncio
async def test_full_purchase_workflow_payable_and_gl_stay_consistent(
    client, auth_headers, test_company, db_session
):
    product, warehouse, supplier = await create_purchase_context(
        client, auth_headers, test_company, db_session, "FLOW"
    )

    # ── 1. Purchase order → approved ───────────────────────────────────────
    po_res = await client.post(
        "/api/v1/purchase-orders/",
        json={
            "supplier_id": supplier["id"],
            "warehouse_id": str(warehouse.id),
            "expected_delivery_date": (date.today() + timedelta(days=10)).isoformat(),
            "notes": "E2E purchase order",
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
        json={"status": "approved", "notes": "Approved for receipt"},
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text

    # ── 2. Goods receipt (full 5 units) → stock increases ──────────────────
    receipt_res = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={
            "idempotency_key": "e2e-purchase-receipt",
            "notes": "Full delivery",
            "items": [{"purchase_order_item_id": po_item_id, "quantity": 5}],
        },
        headers=auth_headers,
    )
    assert receipt_res.status_code == 200, receipt_res.text
    assert receipt_res.json()["data"]["status"] == "posted"

    await db_session.refresh(product)
    balance = (
        await db_session.execute(
            select(InventoryBalance).where(
                InventoryBalance.company_id == test_company.id,
                InventoryBalance.product_id == product.id,
            )
        )
    ).scalar_one()
    assert balance.quantity == Decimal("5")
    assert product.current_stock == 5.0

    movements = (
        await db_session.execute(
            select(InventoryMovement).where(
                InventoryMovement.company_id == test_company.id,
                InventoryMovement.product_id == product.id,
                InventoryMovement.reason == "purchase_order_receipt",
            )
        )
    ).scalars().all()
    assert len(movements) == 1

    # ── 3. Supplier invoice → payable + GL entry ───────────────────────────
    invoice_res = await client.post(
        "/api/v1/supplier-invoices/",
        json={
            "supplier_id": supplier["id"],
            "purchase_order_id": po["id"],
            "supplier_invoice_number": f"SUP-INV-E2E-{date.today().isoformat()}",
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
    assert invoice["total"] == 59  # 50 + 9 VAT
    assert invoice["status"] == "draft"

    approved_res = await client.patch(
        f"/api/v1/supplier-invoices/{invoice['id']}/status",
        json={"status": "approved", "notes": "Finance approval"},
        headers=auth_headers,
    )
    assert approved_res.status_code == 200, approved_res.text
    approved_invoice = approved_res.json()["data"]
    assert approved_invoice["status"] == "approved"
    payable_id = approved_invoice["payable"]["id"]

    # ── 4. Payment → payable closed + GL entry ─────────────────────────────
    payment_res = await client.post(
        f"/api/v1/supplier-payables/{payable_id}/payments",
        json={
            "idempotency_key": "e2e-purchase-payment",
            "amount": 59,
            "payment_date": date.today().isoformat(),
            "payment_method": "bank_transfer",
            "reference": "E2E-SUP-PAY-001",
        },
        headers=auth_headers,
    )
    assert payment_res.status_code == 200, payment_res.text
    payable = payment_res.json()["data"]
    assert payable["status"] == "paid"

    # ── 5. GL: balanced entries exist for invoice and payment ──────────────
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

    # ── 6. Supplier Finance totals reflect the payable lifecycle ───────────
    payables_res = await client.get(
        "/api/v1/supplier-payables/?page_size=100",
        headers=auth_headers,
    )
    assert payables_res.status_code == 200
    payables = payables_res.json()["data"]["items"]
    assert any(p["id"] == payable_id and p["status"] == "paid" for p in payables)


@pytest.mark.asyncio
async def test_purchase_receipt_over_delivery_is_rejected(
    client, auth_headers, test_company, db_session
):
    product, warehouse, supplier = await create_purchase_context(
        client, auth_headers, test_company, db_session, "OVER"
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
                    "quantity": 2,
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

    over_receipt = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={
            "idempotency_key": "e2e-purchase-over-receipt",
            "items": [{"purchase_order_item_id": po_item_id, "quantity": 3}],
        },
        headers=auth_headers,
    )
    assert over_receipt.status_code == 409, over_receipt.text

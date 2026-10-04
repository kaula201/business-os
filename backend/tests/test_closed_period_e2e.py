"""E2 — Closed accounting period rules, end-to-end.

Verifies that a closed period blocks every money-moving operation, including
customer payments, supplier payments, and invoice issuance — not just the
GL/cash/expense paths already covered by unit tests.
"""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.product import Product
from app.models.receivable import CustomerReceivable
from app.models.warehouse import InventoryBalance, Warehouse


async def create_e2_sales_context(client, auth_headers, test_company, db_session, suffix: str):
    product = Product(
        company_id=test_company.id,
        sku=f"E2-SALE-{suffix}",
        name=f"E2 Sale Product {suffix}",
        sale_price=100,
        purchase_price=50,
        unit="ცალი",
        min_stock=0,
        current_stock=100,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code=f"E2-SALE-WH-{suffix}",
        name=f"E2 Sale Warehouse {suffix}",
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
            "name": f"E2 Client {suffix}",
            "client_type": "legal",
            "identification_code": f"{uuid4().int % 900000000 + 100000000}",
            "status": "active",
            "is_vat_payer": False,
        },
        headers=auth_headers,
    )
    assert client_res.status_code == 200, client_res.text
    return product, warehouse, client_res.json()["data"]


async def create_issued_receivable(client, auth_headers, test_company, db_session, suffix: str):
    product, warehouse, customer = await create_e2_sales_context(
        client, auth_headers, test_company, db_session, suffix
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
            "idempotency_key": f"e2-{suffix}-invoice",
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
        },
        headers=auth_headers,
    )
    assert invoice_res.status_code == 200, invoice_res.text

    receivable = (
        await db_session.execute(
            select(CustomerReceivable).where(
                CustomerReceivable.company_id == test_company.id
            )
        )
    ).scalars().one()
    return receivable


@pytest.mark.asyncio
async def test_closed_period_blocks_customer_payment(
    client, auth_headers, test_company, db_session
):
    receivable = await create_issued_receivable(
        client, auth_headers, test_company, db_session, "PAY-LOCK"
    )

    closed = await client.post(
        "/api/v1/accounting-periods/2026/7/close",
        headers=auth_headers,
        json={"reason": "ივლისის საბოლოო დახურვა"},
    )
    assert closed.status_code == 200

    # Payment dated in the closed period must be blocked.
    payment = await client.post(
        f"/api/v1/customer-receivables/{receivable.id}/payments",
        json={
            "idempotency_key": "e2-closed-period-payment",
            "amount": 100,
            "payment_date": "2026-07-15",
            "payment_method": "bank_transfer",
            "reference": "E2-CLOSED-PAY",
        },
        headers=auth_headers,
    )
    assert payment.status_code == 409, payment.text
    assert "დახურულია" in payment.json()["detail"], payment.text

    # Receivable unchanged.
    await db_session.refresh(receivable)
    assert receivable.paid_amount == Decimal("0")
    assert receivable.outstanding_amount == Decimal("500")


@pytest.mark.asyncio
async def test_closed_period_blocks_invoice_issuance(
    client, auth_headers, test_company, db_session
):
    product, warehouse, customer = await create_e2_sales_context(
        client, auth_headers, test_company, db_session, "INV-LOCK"
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
                    "quantity": 2,
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

    closed = await client.post(
        "/api/v1/accounting-periods/2026/7/close",
        headers=auth_headers,
        json={"reason": "ივლისის საბოლოო დახურვა"},
    )
    assert closed.status_code == 200

    # Invoice dated in the closed period must be blocked.
    invoice_res = await client.post(
        "/api/v1/invoices/generate",
        json={
            "order_id": order_id,
            "idempotency_key": "e2-closed-period-invoice",
            "invoice_date": "2026-07-20",
            "due_date": "2026-08-03",
        },
        headers=auth_headers,
    )
    assert invoice_res.status_code == 409, invoice_res.text
    assert "დახურულია" in invoice_res.json()["detail"], invoice_res.text


@pytest.mark.asyncio
async def test_closed_period_blocks_supplier_payment(
    client, auth_headers, test_company, db_session
):
    product = Product(
        company_id=test_company.id,
        sku="E2-SUP-LOCK",
        name="E2 Supplier Lock Product",
        sale_price=30,
        purchase_price=10,
        unit="ცალი",
        min_stock=0,
        current_stock=0,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code="E2-SUP-LOCK-WH",
        name="E2 Supplier Lock WH",
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
            "code": "E2-SUP-LOCK",
            "name": "E2 Supplier Lock",
            "identification_code": f"{uuid4().int % 900000000 + 100000000}",
            "is_vat_payer": True,
            "contact_name": "E2 Contact",
            "phone": "+995500000003",
            "email": "e2suplock@supplier.ge",
            "payment_terms_days": 30,
        },
        headers=auth_headers,
    )
    assert supplier_res.status_code == 200, supplier_res.text
    supplier = supplier_res.json()["data"]

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
            "idempotency_key": "e2-sup-lock-receipt",
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
            "supplier_invoice_number": "E2-SUP-LOCK-INV",
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
    approved_inv = await client.patch(
        f"/api/v1/supplier-invoices/{invoice['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved_inv.status_code == 200, approved_inv.text
    payable_id = approved_inv.json()["data"]["payable"]["id"]

    closed = await client.post(
        "/api/v1/accounting-periods/2026/7/close",
        headers=auth_headers,
        json={"reason": "ივლისის საბოლოო დახურვა"},
    )
    assert closed.status_code == 200

    payment = await client.post(
        f"/api/v1/supplier-payables/{payable_id}/payments",
        json={
            "idempotency_key": "e2-closed-period-sup-pay",
            "amount": 59,
            "payment_date": "2026-07-15",
            "payment_method": "bank_transfer",
            "reference": "E2-CLOSED-SUP-PAY",
        },
        headers=auth_headers,
    )
    assert payment.status_code == 409, payment.text
    assert "დახურულია" in payment.json()["detail"], payment.text

import asyncio
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.product import Product
from app.models.warehouse import Warehouse


async def setup_received_purchase(
    client,
    auth_headers,
    test_company,
    db_session,
    suffix: str,
    *,
    quantity: float = 10,
    unit_price: float = 10,
):
    product = Product(
        company_id=test_company.id,
        sku=f"PAY-{suffix}",
        name=f"Payable Product {suffix}",
        sale_price=20,
        purchase_price=unit_price,
        unit="ცალი",
        min_stock=0,
        current_stock=0,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code=f"PAY-{suffix}",
        name=f"Payable Warehouse {suffix}",
        is_default=False,
        is_active=True,
    )
    db_session.add_all([product, warehouse])
    await db_session.commit()
    await db_session.refresh(product)
    await db_session.refresh(warehouse)

    supplier_response = await client.post(
        "/api/v1/suppliers/",
        json={
            "code": f"PAY-{suffix}",
            "name": f"Payable Supplier {suffix}",
            "payment_terms_days": 30,
        },
        headers=auth_headers,
    )
    assert supplier_response.status_code == 200, supplier_response.text
    supplier = supplier_response.json()["data"]

    po_response = await client.post(
        "/api/v1/purchase-orders/",
        json={
            "supplier_id": supplier["id"],
            "warehouse_id": str(warehouse.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_percent": 0,
                    "vat_rate": 0,
                }
            ],
        },
        headers=auth_headers,
    )
    assert po_response.status_code == 200, po_response.text
    purchase_order = po_response.json()["data"]

    approved = await client.patch(
        f"/api/v1/purchase-orders/{purchase_order['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text

    receipt = await client.post(
        f"/api/v1/purchase-orders/{purchase_order['id']}/receipts",
        json={
            "idempotency_key": f"payable-receipt-{suffix}",
            "items": [
                {
                    "purchase_order_item_id": purchase_order["items"][0]["id"],
                    "quantity": quantity,
                }
            ],
        },
        headers=auth_headers,
    )
    assert receipt.status_code == 200, receipt.text
    return supplier, purchase_order


async def create_supplier_invoice(
    client,
    auth_headers,
    supplier,
    purchase_order,
    suffix: str,
    *,
    quantity: float = 10,
    unit_price: float = 10,
    due_date: date | None = None,
):
    invoice_date = (
        due_date - timedelta(days=30)
        if due_date and due_date < date.today()
        else date.today()
    )
    response = await client.post(
        "/api/v1/supplier-invoices/",
        json={
            "supplier_id": supplier["id"],
            "purchase_order_id": purchase_order["id"],
            "supplier_invoice_number": f"VENDOR-{suffix}",
            "invoice_date": str(invoice_date),
            "due_date": str(due_date or (date.today() + timedelta(days=30))),
            "notes": "Payable integration test",
            "items": [
                {
                    "purchase_order_item_id": purchase_order["items"][0]["id"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_percent": 0,
                    "vat_rate": 0,
                }
            ],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_matched_supplier_invoice_creates_payable_and_supports_idempotent_payments(
    client, auth_headers, test_company, db_session
):
    supplier, purchase_order = await setup_received_purchase(
        client, auth_headers, test_company, db_session, "MATCHED"
    )
    invoice = await create_supplier_invoice(
        client, auth_headers, supplier, purchase_order, "MATCHED"
    )
    assert invoice["status"] == "draft"
    assert invoice["matching_status"] == "matched"
    assert invoice["total"] == 100
    assert invoice["payable"] is None

    approved = await client.patch(
        f"/api/v1/supplier-invoices/{invoice['id']}/status",
        json={"status": "approved", "notes": "Finance approval"},
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text
    approved_invoice = approved.json()["data"]
    payable = approved_invoice["payable"]
    assert approved_invoice["status"] == "approved"
    assert payable["status"] == "unpaid"
    assert payable["original_amount"] == 100
    assert payable["paid_amount"] == 0
    assert payable["outstanding_amount"] == 100

    partial_payload = {
        "idempotency_key": "payment-matched-partial",
        "amount": 40,
        "payment_date": str(date.today()),
        "payment_method": "bank_transfer",
        "reference": "BANK-001",
    }
    partial = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/payments",
        json=partial_payload,
        headers=auth_headers,
    )
    assert partial.status_code == 200, partial.text
    partial_payable = partial.json()["data"]
    assert partial_payable["status"] == "partially_paid"
    assert partial_payable["paid_amount"] == 40
    assert partial_payable["outstanding_amount"] == 60
    assert len(partial_payable["payments"]) == 1

    duplicate = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/payments",
        json=partial_payload,
        headers=auth_headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["paid_amount"] == 40
    assert len(duplicate.json()["data"]["payments"]) == 1

    overpayment = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/payments",
        json={
            "idempotency_key": "payment-over",
            "amount": 61,
            "payment_date": str(date.today()),
            "payment_method": "bank_transfer",
        },
        headers=auth_headers,
    )
    assert overpayment.status_code == 409

    final = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/payments",
        json={
            "idempotency_key": "payment-final",
            "amount": 60,
            "payment_date": str(date.today()),
            "payment_method": "bank_transfer",
        },
        headers=auth_headers,
    )
    assert final.status_code == 200
    final_payable = final.json()["data"]
    assert final_payable["status"] == "paid"
    assert final_payable["paid_amount"] == 100
    assert final_payable["outstanding_amount"] == 0
    assert len(final_payable["payments"]) == 2


@pytest.mark.asyncio
async def test_mismatched_supplier_invoice_cannot_be_approved(
    client, auth_headers, test_company, db_session
):
    supplier, purchase_order = await setup_received_purchase(
        client, auth_headers, test_company, db_session, "MISMATCH"
    )
    invoice = await create_supplier_invoice(
        client,
        auth_headers,
        supplier,
        purchase_order,
        "MISMATCH",
        unit_price=11,
    )
    assert invoice["matching_status"] == "amount_mismatch"
    assert invoice["match_issues"]

    approved = await client.patch(
        f"/api/v1/supplier-invoices/{invoice['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved.status_code == 409

    fetched = await client.get(
        f"/api/v1/supplier-invoices/{invoice['id']}", headers=auth_headers
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["status"] == "draft"
    assert fetched.json()["data"]["payable"] is None


@pytest.mark.asyncio
async def test_approved_past_due_invoice_is_reported_overdue(
    client, auth_headers, test_company, db_session
):
    supplier, purchase_order = await setup_received_purchase(
        client, auth_headers, test_company, db_session, "OVERDUE"
    )
    invoice = await create_supplier_invoice(
        client,
        auth_headers,
        supplier,
        purchase_order,
        "OVERDUE",
        due_date=date.today() - timedelta(days=1),
    )
    approved = await client.patch(
        f"/api/v1/supplier-invoices/{invoice['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved.status_code == 200
    payable = approved.json()["data"]["payable"]
    assert payable["status"] == "overdue"
    assert payable["days_overdue"] == 1

    listed = await client.get(
        "/api/v1/supplier-payables/?status=overdue", headers=auth_headers
    )
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1
    assert listed.json()["data"]["items"][0]["id"] == payable["id"]


@pytest.mark.asyncio
async def test_concurrent_payments_cannot_overpay_payable(
    client, auth_headers, test_company, db_session
):
    supplier, purchase_order = await setup_received_purchase(
        client, auth_headers, test_company, db_session, "CONCURRENT"
    )
    invoice = await create_supplier_invoice(
        client, auth_headers, supplier, purchase_order, "CONCURRENT"
    )
    approved = await client.patch(
        f"/api/v1/supplier-invoices/{invoice['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    payable = approved.json()["data"]["payable"]

    async def pay(key: str):
        return await client.post(
            f"/api/v1/supplier-payables/{payable['id']}/payments",
            json={
                "idempotency_key": key,
                "amount": 70,
                "payment_date": str(date.today()),
                "payment_method": "bank_transfer",
            },
            headers=auth_headers,
        )

    responses = await asyncio.gather(pay("concurrent-a"), pay("concurrent-b"))
    assert sorted(response.status_code for response in responses) == [200, 409]
    current = await client.get(
        f"/api/v1/supplier-payables/{payable['id']}", headers=auth_headers
    )
    assert current.status_code == 200
    assert current.json()["data"]["paid_amount"] == 70
    assert current.json()["data"]["outstanding_amount"] == 30
    assert len(current.json()["data"]["payments"]) == 1


@pytest.mark.asyncio
async def test_cumulative_invoicing_cannot_exceed_received_quantity(
    client, auth_headers, test_company, db_session
):
    supplier, purchase_order = await setup_received_purchase(
        client, auth_headers, test_company, db_session, "CUMULATIVE"
    )
    first = await create_supplier_invoice(
        client, auth_headers, supplier, purchase_order, "CUMULATIVE-A", quantity=6
    )
    assert first["matching_status"] == "matched"

    second = await create_supplier_invoice(
        client, auth_headers, supplier, purchase_order, "CUMULATIVE-B", quantity=5
    )
    assert second["matching_status"] == "quantity_mismatch"
    assert any("დაუფაქტურებელ" in issue for issue in second["match_issues"])

    approval = await client.patch(
        f"/api/v1/supplier-invoices/{second['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approval.status_code == 409


@pytest.mark.asyncio
async def test_supplier_invoice_number_is_unique_per_supplier(
    client, auth_headers, test_company, db_session
):
    supplier, purchase_order = await setup_received_purchase(
        client, auth_headers, test_company, db_session, "DUPLICATE"
    )
    await create_supplier_invoice(
        client, auth_headers, supplier, purchase_order, "DUPLICATE", quantity=4
    )
    duplicate = await client.post(
        "/api/v1/supplier-invoices/",
        json={
            "supplier_id": supplier["id"],
            "purchase_order_id": purchase_order["id"],
            "supplier_invoice_number": "VENDOR-DUPLICATE",
            "invoice_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=30)),
            "items": [{
                "purchase_order_item_id": purchase_order["items"][0]["id"],
                "quantity": 1,
                "unit_price": 10,
                "discount_percent": 0,
                "vat_rate": 0,
            }],
        },
        headers=auth_headers,
    )
    assert duplicate.status_code == 409

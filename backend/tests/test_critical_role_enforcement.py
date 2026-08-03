from datetime import date
from uuid import uuid4

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_employee_cannot_decide_expense(client, employee_auth_headers, action):
    response = await client.post(
        f"/api/v1/expenses/{uuid4()}/{action}",
        headers=employee_auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_post_supplier_payment(client, employee_auth_headers):
    response = await client.post(
        f"/api/v1/supplier-payables/{uuid4()}/payments",
        json={
            "idempotency_key": "employee-payment-denied",
            "amount": "10.00",
            "payment_date": date.today().isoformat(),
            "payment_method": "bank_transfer",
        },
        headers=employee_auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_post_goods_receipt(client, employee_auth_headers):
    response = await client.post(
        f"/api/v1/purchase-orders/{uuid4()}/receipts",
        json={
            "idempotency_key": "employee-receipt-denied",
            "items": [
                {"purchase_order_item_id": str(uuid4()), "quantity": "1.000"}
            ],
        },
        headers=employee_auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_run_depreciation(client, employee_auth_headers):
    response = await client.post(
        f"/api/v1/assets/{uuid4()}/run-depreciation",
        headers=employee_auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_approve_supplier_invoice(client, employee_auth_headers):
    response = await client.patch(
        f"/api/v1/supplier-invoices/{uuid4()}/status",
        json={"status": "approved"},
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_create_cash_account(client, employee_auth_headers):
    response = await client.post(
        "/api/v1/cash/accounts",
        json={"name": "Unauthorized Cash", "currency": "GEL"},
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_create_fixed_asset(client, employee_auth_headers):
    response = await client.post(
        "/api/v1/assets/",
        json={
            "name": "Unauthorized Asset",
            "asset_type": "equipment",
            "purchase_date": date.today().isoformat(),
            "purchase_cost": "100.00",
            "useful_life_years": 3,
        },
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_create_analytic_account(client, employee_auth_headers):
    response = await client.post(
        "/api/v1/analytic/accounts",
        json={"code": "UNAUTHORIZED", "name": "Unauthorized Analytic"},
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_create_currency_rate(client, employee_auth_headers):
    response = await client.post(
        "/api/v1/currency/rates",
        json={
            "from_currency": "USD",
            "to_currency": "GEL",
            "rate_date": date.today().isoformat(),
            "rate": "2.700000",
        },
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_change_order_status(client, employee_auth_headers):
    response = await client.patch(
        f"/api/v1/orders/{uuid4()}/status",
        json={"status": "confirmed"},
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_adjust_product_stock(client, employee_auth_headers):
    response = await client.post(
        "/api/v1/products/adjust-stock",
        json={
            "product_id": str(uuid4()),
            "movement_type": "in",
            "quantity": 1,
            "reason": "inventory",
        },
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_adjust_warehouse_stock(client, employee_auth_headers):
    response = await client.post(
        "/api/v1/warehouses/adjust-stock",
        json={
            "product_id": str(uuid4()),
            "warehouse_id": str(uuid4()),
            "movement_type": "in",
            "quantity": 1,
            "reason": "inventory",
        },
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_transfer_warehouse_stock(client, employee_auth_headers):
    response = await client.post(
        "/api/v1/warehouses/transfers",
        json={
            "product_id": str(uuid4()),
            "source_warehouse_id": str(uuid4()),
            "destination_warehouse_id": str(uuid4()),
            "quantity": 1,
            "reason": "transfer",
        },
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_import_clients(client, employee_auth_headers):
    response = await client.post(
        "/api/v1/import/clients",
        files={
            "file": (
                "unauthorized.xlsx",
                b"not-an-excel-file",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_export_full_client_dataset(client, employee_auth_headers):
    response = await client.get(
        "/api/v1/export/clients",
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_reindex_company(client, employee_auth_headers):
    response = await client.post(
        "/api/v1/ai/reindex",
        headers=employee_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/budgeting/plans/{id}",
        "/api/v1/clients/{id}",
        "/api/v1/fleet/vehicles/{id}",
        "/api/v1/fleet/fuel-logs/{id}",
        "/api/v1/fleet/services/{id}",
        "/api/v1/fleet/drivers/{id}",
        "/api/v1/warehouses/{id}",
    ],
)
async def test_employee_cannot_delete_domain_records(client, employee_auth_headers, path):
    response = await client.delete(
        path.format(id=uuid4()),
        headers=employee_auth_headers,
    )
    assert response.status_code == 403

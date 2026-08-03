# backend/tests/test_orders.py
from decimal import Decimal

import pytest

from app.models.client import Client
from app.models.product import Product
from app.models.warehouse import InventoryBalance, Warehouse


async def create_order_dependencies(db_session, company_id, suffix: str):
    client_obj = Client(
        company_id=company_id,
        name=f"Test Client {suffix}",
        client_type="legal",
        identification_code=f"ID-{suffix}",
        status="active",
    )
    product = Product(
        company_id=company_id,
        sku=f"SKU-{suffix}",
        name=f"Order Test Product {suffix}",
        sale_price=100.0,
        current_stock=20,
    )
    db_session.add_all([client_obj, product])
    await db_session.commit()
    await db_session.refresh(client_obj)
    await db_session.refresh(product)
    return client_obj, product


@pytest.mark.asyncio
async def test_create_order(client, auth_headers, test_company, db_session):
    client_obj, product = await create_order_dependencies(
        db_session, test_company.id, "CREATE"
    )

    response = await client.post(
        "/api/v1/orders/",
        json={
            "client_id": str(client_obj.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "quantity": 2,
                    "unit_price": 100.0,
                    "discount_percent": 0,
                }
            ],
            "delivery_address": "თბილისი",
            "notes": "Test order",
            "is_vat_payer": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["order_number"].startswith("ORD-")
    assert float(data["total"]) == 236.0


@pytest.mark.asyncio
async def test_list_orders(client, auth_headers):
    response = await client.get("/api/v1/orders/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_change_order_status(client, auth_headers, test_company, db_session):
    client_obj, product = await create_order_dependencies(
        db_session, test_company.id, "STATUS"
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code="ORDER-STATUS-WH",
        name="Order Status Warehouse",
        is_default=True,
        is_active=True,
    )
    db_session.add(warehouse)
    await db_session.flush()
    db_session.add(
        InventoryBalance(
            company_id=test_company.id,
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=Decimal("20"),
        )
    )
    await db_session.commit()
    await db_session.refresh(warehouse)

    create_res = await client.post(
        "/api/v1/orders/",
        json={
            "client_id": str(client_obj.id),
            "warehouse_id": str(warehouse.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "quantity": 1,
                    "unit_price": 50.0,
                }
            ],
            "is_vat_payer": False,
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    order_id = create_res.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "confirmed", "notes": "Confirmed by admin"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "confirmed"

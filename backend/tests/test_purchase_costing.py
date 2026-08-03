from decimal import Decimal

import pytest

from app.models.product import Product
from app.models.warehouse import InventoryBalance, Warehouse


async def create_received_order(
    client,
    auth_headers,
    supplier_id: str,
    warehouse_id: str,
    product_id: str,
    suffix: str,
    *,
    quantity: float,
    unit_price: float,
    discount_percent: float = 0,
    idempotency_key: str,
):
    created = await client.post(
        "/api/v1/purchase-orders/",
        json={
            "supplier_id": supplier_id,
            "warehouse_id": warehouse_id,
            "items": [{
                "product_id": product_id,
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_percent": discount_percent,
                "vat_rate": 18,
            }],
            "notes": f"Costing test {suffix}",
        },
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    order = created.json()["data"]
    approved = await client.patch(
        f"/api/v1/purchase-orders/{order['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text
    receipt_payload = {
        "idempotency_key": idempotency_key,
        "items": [{
            "purchase_order_item_id": order["items"][0]["id"],
            "quantity": quantity,
        }],
    }
    receipt = await client.post(
        f"/api/v1/purchase-orders/{order['id']}/receipts",
        json=receipt_payload,
        headers=auth_headers,
    )
    assert receipt.status_code == 200, receipt.text
    return order, receipt_payload, receipt.json()["data"]


@pytest.mark.asyncio
async def test_goods_receipts_update_weighted_average_cost_and_immutable_history(
    client, auth_headers, test_company, db_session
):
    product = Product(
        company_id=test_company.id,
        sku="COST-001",
        name="Costed Product",
        sale_price=40,
        purchase_price=10,
        unit="ცალი",
        min_stock=0,
        current_stock=10,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code="COST-WH",
        name="Cost Warehouse",
        is_default=False,
        is_active=True,
    )
    db_session.add_all([product, warehouse])
    await db_session.flush()
    db_session.add(InventoryBalance(
        company_id=test_company.id,
        warehouse_id=warehouse.id,
        product_id=product.id,
        quantity=Decimal("10"),
    ))
    await db_session.commit()
    await db_session.refresh(product)
    await db_session.refresh(warehouse)

    supplier_response = await client.post(
        "/api/v1/suppliers/",
        json={"code": "COST-SUP", "name": "Cost Supplier"},
        headers=auth_headers,
    )
    assert supplier_response.status_code == 200
    supplier_id = supplier_response.json()["data"]["id"]

    first_order, first_payload, _ = await create_received_order(
        client,
        auth_headers,
        supplier_id,
        str(warehouse.id),
        str(product.id),
        "first",
        quantity=10,
        unit_price=20,
        discount_percent=10,
        idempotency_key="cost-receipt-first",
    )

    history = await client.get(
        f"/api/v1/purchase-cost-history/?product_id={product.id}",
        headers=auth_headers,
    )
    assert history.status_code == 200, history.text
    first_history = history.json()["data"]
    assert first_history["total"] == 1
    first = first_history["items"][0]
    assert first["purchase_order_id"] == first_order["id"]
    assert first["quantity"] == 10
    assert first["unit_cost"] == 18
    assert first["previous_stock"] == 10
    assert first["new_stock"] == 20
    assert first["previous_average_cost"] == 10
    assert first["new_average_cost"] == 14

    product_response = await client.get(f"/api/v1/products/{product.id}", headers=auth_headers)
    assert product_response.status_code == 200
    assert product_response.json()["data"]["average_cost"] == 14
    assert product_response.json()["data"]["purchase_price"] == 14

    _, _, _ = await create_received_order(
        client,
        auth_headers,
        supplier_id,
        str(warehouse.id),
        str(product.id),
        "second",
        quantity=10,
        unit_price=30,
        idempotency_key="cost-receipt-second",
    )
    product_response = await client.get(f"/api/v1/products/{product.id}", headers=auth_headers)
    assert product_response.json()["data"]["average_cost"] == pytest.approx(19.3333, abs=0.0001)

    duplicate = await client.post(
        f"/api/v1/purchase-orders/{first_order['id']}/receipts",
        json=first_payload,
        headers=auth_headers,
    )
    assert duplicate.status_code == 200
    final_history = await client.get(
        f"/api/v1/purchase-cost-history/?product_id={product.id}",
        headers=auth_headers,
    )
    assert final_history.status_code == 200
    assert final_history.json()["data"]["total"] == 2
    final_product = await client.get(f"/api/v1/products/{product.id}", headers=auth_headers)
    assert final_product.json()["data"]["average_cost"] == pytest.approx(19.3333, abs=0.0001)


@pytest.mark.asyncio
async def test_rejected_receipt_does_not_change_average_cost_history(
    client, auth_headers, test_company, db_session
):
    product = Product(
        company_id=test_company.id,
        sku="COST-REJECT",
        name="Rejected Cost Product",
        sale_price=30,
        purchase_price=12,
        unit="ცალი",
        min_stock=0,
        current_stock=0,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code="COST-RJ",
        name="Rejected Cost Warehouse",
        is_default=False,
        is_active=True,
    )
    db_session.add_all([product, warehouse])
    await db_session.commit()
    await db_session.refresh(product)
    await db_session.refresh(warehouse)
    supplier = await client.post(
        "/api/v1/suppliers/",
        json={"code": "COST-RJ", "name": "Rejected Cost Supplier"},
        headers=auth_headers,
    )
    order = await client.post(
        "/api/v1/purchase-orders/",
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "warehouse_id": str(warehouse.id),
            "items": [{
                "product_id": str(product.id),
                "quantity": 5,
                "unit_price": 20,
                "discount_percent": 0,
                "vat_rate": 18,
            }],
        },
        headers=auth_headers,
    )
    order_data = order.json()["data"]
    await client.patch(
        f"/api/v1/purchase-orders/{order_data['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    rejected = await client.post(
        f"/api/v1/purchase-orders/{order_data['id']}/receipts",
        json={
            "idempotency_key": "cost-rejected",
            "items": [{
                "purchase_order_item_id": order_data["items"][0]["id"],
                "quantity": 6,
            }],
        },
        headers=auth_headers,
    )
    assert rejected.status_code == 409
    history = await client.get(
        f"/api/v1/purchase-cost-history/?product_id={product.id}",
        headers=auth_headers,
    )
    assert history.status_code == 200
    assert history.json()["data"]["total"] == 0

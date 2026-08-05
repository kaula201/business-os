import pytest
from sqlalchemy import update

from app.models.product import Product


@pytest.mark.asyncio
async def test_dashboard_low_stock_uses_warehouse_balances(
    client, auth_headers, db_session
):
    warehouse_response = await client.post(
        "/api/v1/warehouses/",
        json={
            "code": "MAIN",
            "name": "მთავარი საწყობი",
            "is_default": True,
        },
        headers=auth_headers,
    )
    assert warehouse_response.status_code == 200
    warehouse_id = warehouse_response.json()["data"]["id"]

    product_response = await client.post(
        "/api/v1/products/",
        json={
            "sku": "DASH-STOCK-001",
            "name": "Dashboard Stock Product",
            "sale_price": 10,
            "min_stock": 10,
        },
        headers=auth_headers,
    )
    assert product_response.status_code == 200
    product_id = product_response.json()["data"]["id"]

    stock_response = await client.post(
        "/api/v1/warehouses/adjust-stock",
        json={
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "movement_type": "in",
            "quantity": 5,
            "reason": "initial_stock",
        },
        headers=auth_headers,
    )
    assert stock_response.status_code == 200

    # Simulate a stale denormalized Product.current_stock value. Dashboard must
    # still use the canonical sum of inventory_balances (5), not this value.
    await db_session.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(current_stock=100)
    )
    await db_session.commit()

    dashboard_response = await client.get(
        "/api/v1/dashboard/summary?period=7d",
        headers=auth_headers,
    )
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()["data"]

    assert dashboard["kpi"]["low_stock_products"] == 1
    stock_alert = next(
        alert
        for alert in dashboard["critical_alerts"]
        if alert["entity_id"] == product_id
    )
    assert stock_alert["description"] == "მიმდინარე ნაშთი: 5.0 ცალი"
    assert stock_alert["severity"] == "medium"

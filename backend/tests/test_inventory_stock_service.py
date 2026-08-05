import pytest
from sqlalchemy import select, update

from app.models.product import Product


@pytest.mark.asyncio
async def test_sync_product_current_stock_uses_balance_sum(
    client, auth_headers, db_session
):
    warehouse_response = await client.post(
        "/api/v1/warehouses/",
        json={"code": "MAIN", "name": "მთავარი საწყობი", "is_default": True},
        headers=auth_headers,
    )
    warehouse_id = warehouse_response.json()["data"]["id"]

    product_response = await client.post(
        "/api/v1/products/",
        json={"sku": "SYNC-STOCK-001", "name": "Sync Stock", "sale_price": 10},
        headers=auth_headers,
    )
    product_id = product_response.json()["data"]["id"]

    await client.post(
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
    await db_session.execute(
        update(Product).where(Product.id == product_id).values(current_stock=99)
    )
    await db_session.commit()

    from app.services.inventory import sync_product_current_stock

    company_id = (
        await db_session.execute(
            select(Product.company_id).where(Product.id == product_id)
        )
    ).scalar_one()

    total = await sync_product_current_stock(
        db_session,
        product_id=product_id,
        company_id=company_id,
    )
    await db_session.commit()

    current_stock = (
        await db_session.execute(
            select(Product.current_stock).where(Product.id == product_id)
        )
    ).scalar_one()
    assert total == 5
    assert current_stock == 5

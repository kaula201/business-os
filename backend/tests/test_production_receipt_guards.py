import pytest


async def create_company_warehouse(client, auth_headers, code="MAIN"):
    response = await client.post(
        "/api/v1/warehouses/",
        json={"code": code, "name": "მთავარი საწყობი", "is_default": True},
        headers=auth_headers,
    )
    return response.json()["data"]


async def create_company_product(client, auth_headers, sku, name, price=10):
    response = await client.post(
        "/api/v1/products/",
        json={"sku": sku, "name": name, "sale_price": price},
        headers=auth_headers,
    )
    return response.json()["data"]


async def create_work_order(client, auth_headers, product_id, warehouse_id):
    bom_response = await client.post(
        "/api/v1/production/boms",
        json={
            "code": "BOM-REV-001",
            "name": "Review BOM",
            "product_id": product_id,
            "quantity": 1,
        },
        headers=auth_headers,
    )
    bom_id = bom_response.json()["data"]["id"]
    wo_response = await client.post(
        "/api/v1/production/work-orders",
        json={
            "bom_id": bom_id,
            "product_id": product_id,
            "planned_quantity": 10,
            "warehouse_id": warehouse_id,
        },
        headers=auth_headers,
    )
    assert wo_response.status_code == 201, wo_response.text
    wo_id = wo_response.json()["data"]["id"]
    start = await client.patch(
        f"/api/v1/production/work-orders/{wo_id}",
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    assert start.status_code == 200, start.text
    return wo_id


@pytest.mark.asyncio
async def test_receipt_requires_positive_quantity(client, auth_headers):
    warehouse = await create_company_warehouse(client, auth_headers)
    product = await create_company_product(client, auth_headers, "REC-QTY-001", "Receipt Qty")
    wo_id = await create_work_order(client, auth_headers, product["id"], warehouse["id"])

    response = await client.post(
        f"/api/v1/production/work-orders/{wo_id}/receipts",
        json={
            "work_order_id": wo_id,
            "product_id": product["id"],
            "warehouse_id": warehouse["id"],
            "quantity": 0,
            "unit_cost": 5,
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "რაოდენობა დადებითი უნდა იყოს"


@pytest.mark.asyncio
async def test_receipt_rejects_unrelated_product(client, auth_headers):
    warehouse = await create_company_warehouse(client, auth_headers)
    product = await create_company_product(client, auth_headers, "REC-PROD-001", "Receipt Product")
    other = await create_company_product(client, auth_headers, "REC-PROD-002", "Other Product")
    wo_id = await create_work_order(client, auth_headers, product["id"], warehouse["id"])

    response = await client.post(
        f"/api/v1/production/work-orders/{wo_id}/receipts",
        json={
            "work_order_id": wo_id,
            "product_id": other["id"],
            "warehouse_id": warehouse["id"],
            "quantity": 2,
            "unit_cost": 5,
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "მიღებული პროდუქტი არ ემთხვევა სამუშაო ორდერის პროდუქტს"


@pytest.mark.asyncio
async def test_receipt_rejects_foreign_warehouse(client, auth_headers, other_auth_headers):
    warehouse = await create_company_warehouse(client, auth_headers)
    product = await create_company_product(client, auth_headers, "REC-WH-001", "Receipt WH")
    wo_id = await create_work_order(client, auth_headers, product["id"], warehouse["id"])

    response = await client.post(
        f"/api/v1/production/work-orders/{wo_id}/receipts",
        json={
            "work_order_id": wo_id,
            "product_id": product["id"],
            "warehouse_id": warehouse["id"],
            "quantity": 2,
            "unit_cost": 5,
        },
        headers=other_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_receipt_creates_balance_and_movement(client, auth_headers):
    warehouse = await create_company_warehouse(client, auth_headers)
    product = await create_company_product(client, auth_headers, "REC-OK-001", "Receipt OK")
    wo_id = await create_work_order(client, auth_headers, product["id"], warehouse["id"])

    response = await client.post(
        f"/api/v1/production/work-orders/{wo_id}/receipts",
        json={
            "work_order_id": wo_id,
            "product_id": product["id"],
            "warehouse_id": warehouse["id"],
            "quantity": 3,
            "unit_cost": 5,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text

    balances = await client.get(
        f"/api/v1/warehouses/balances?product_id={product['id']}",
        headers=auth_headers,
    )
    assert balances.status_code == 200
    assert balances.json()["data"][0]["quantity"] == 3

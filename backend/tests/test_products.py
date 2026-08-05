# backend/tests/test_products.py
import pytest


@pytest.mark.asyncio
async def test_create_product(client, auth_headers):
    """Test creating a new product."""
    response = await client.post("/api/v1/products/", json={
        "sku": "TEST-001",
        "name": "Test Product",
        "sale_price": 100.0,
        "purchase_price": 80.0,
        "unit": "ცალი",
        "min_stock": 10,
        "current_stock": 0,
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sku"] == "TEST-001"
    assert data["name"] == "Test Product"
    assert data["sale_price"] == 100.0
    assert float(data["current_stock"]) == 0.0


@pytest.mark.asyncio
async def test_create_product_rejects_initial_stock_without_warehouse(client, auth_headers):
    response = await client.post("/api/v1/products/", json={
        "sku": "NO-WH-STOCK",
        "name": "Warehouse-less Stock",
        "sale_price": 10,
        "current_stock": 5,
    }, headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "საწყისი ნაშთისთვის ჯერ შექმენით აქტიური მთავარი საწყობი"


@pytest.mark.asyncio
async def test_create_product_puts_initial_stock_in_default_warehouse(client, auth_headers):
    warehouse = await client.post("/api/v1/warehouses/", json={
        "code": "MAIN",
        "name": "მთავარი საწყობი",
        "is_default": True,
    }, headers=auth_headers)
    assert warehouse.status_code == 200

    product = await client.post("/api/v1/products/", json={
        "sku": "DEFAULT-WH-STOCK",
        "name": "Default Warehouse Stock",
        "sale_price": 10,
        "current_stock": 5,
    }, headers=auth_headers)
    assert product.status_code == 200
    product_id = product.json()["data"]["id"]

    balances = await client.get(
        f"/api/v1/warehouses/balances?product_id={product_id}",
        headers=auth_headers,
    )
    assert balances.status_code == 200
    assert len(balances.json()["data"]) == 1
    assert balances.json()["data"][0]["quantity"] == 5


@pytest.mark.asyncio
async def test_product_update_rejects_direct_stock_change(client, auth_headers):
    product = await client.post("/api/v1/products/", json={
        "sku": "DIRECT-STOCK-UPDATE",
        "name": "Direct Stock Update",
        "sale_price": 10,
    }, headers=auth_headers)
    product_id = product.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/products/{product_id}",
        json={"current_stock": 7},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "ნაშთი შეცვალეთ საწყობის ოპერაციით"


@pytest.mark.asyncio
async def test_legacy_product_stock_adjustment_is_disabled(client, auth_headers):
    product = await client.post("/api/v1/products/", json={
        "sku": "LEGACY-STOCK",
        "name": "Legacy Stock",
        "sale_price": 10,
    }, headers=auth_headers)
    product_id = product.json()["data"]["id"]

    response = await client.post("/api/v1/products/adjust-stock", json={
        "product_id": product_id,
        "movement_type": "in",
        "quantity": 2,
        "reason": "test",
    }, headers=auth_headers)

    assert response.status_code == 410


@pytest.mark.asyncio
async def test_list_products(client, auth_headers):
    """Test listing products."""
    response = await client.get("/api/v1/products/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_product(client, auth_headers):
    """Test getting a single product."""
    # First create a product
    create_res = await client.post("/api/v1/products/", json={
        "sku": "TEST-002",
        "name": "Get Test Product",
        "sale_price": 50.0,
    }, headers=auth_headers)
    product_id = create_res.json()["data"]["id"]

    # Then fetch it
    response = await client.get(f"/api/v1/products/{product_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == product_id
    assert data["name"] == "Get Test Product"


@pytest.mark.asyncio
async def test_update_product(client, auth_headers):
    """Test updating a product."""
    # Create
    create_res = await client.post("/api/v1/products/", json={
        "sku": "TEST-003",
        "name": "Original Name",
        "sale_price": 200.0,
    }, headers=auth_headers)
    product_id = create_res.json()["data"]["id"]

    # Update
    response = await client.patch(f"/api/v1/products/{product_id}", json={
        "name": "Updated Name",
        "sale_price": 250.0,
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Updated Name"
    assert data["sale_price"] == 250.0


@pytest.mark.asyncio
async def test_filter_products_by_stock_status(client, auth_headers):
    """Test filtering products by stock status."""
    response = await client.get("/api/v1/products/?stock_status=good", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    for item in data["items"]:
        assert item["stock_status"] == "good"


@pytest.mark.asyncio
async def test_list_product_categories_without_trailing_slash(client, auth_headers):
    """Static categories route must not be captured as a product UUID."""
    response = await client.get("/api/v1/products/categories", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"] == []

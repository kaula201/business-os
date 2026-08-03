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
        "current_stock": 50,
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sku"] == "TEST-001"
    assert data["name"] == "Test Product"
    assert data["sale_price"] == 100.0
    assert float(data["current_stock"]) == 50.0


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

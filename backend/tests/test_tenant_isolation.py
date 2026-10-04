from datetime import date

import pytest


@pytest.mark.asyncio
async def test_products_are_isolated_between_companies(
    client,
    auth_headers,
    other_auth_headers,
):
    created = await client.post(
        "/api/v1/products/",
        json={
            "sku": "OTHER-PRODUCT-001",
            "name": "Other Company Product",
            "sale_price": 100,
        },
        headers=other_auth_headers,
    )
    assert created.status_code == 200
    product_id = created.json()["data"]["id"]

    listed = await client.get("/api/v1/products/", headers=auth_headers)
    assert listed.status_code == 200
    assert all(item["id"] != product_id for item in listed.json()["data"]["items"])

    fetched = await client.get(f"/api/v1/products/{product_id}", headers=auth_headers)
    assert fetched.status_code == 404

    updated = await client.patch(
        f"/api/v1/products/{product_id}",
        json={"name": "Cross-tenant update"},
        headers=auth_headers,
    )
    assert updated.status_code == 404


@pytest.mark.asyncio
async def test_clients_are_isolated_between_companies(
    client,
    auth_headers,
    other_auth_headers,
):
    created = await client.post(
        "/api/v1/clients/",
        json={
            "client_type": "legal",
            "name": "Other Company Client",
            "identification_code": "200020001",
            "is_vat_payer": True,
        },
        headers=other_auth_headers,
    )
    assert created.status_code == 200
    client_id = created.json()["data"]["id"]

    listed = await client.get("/api/v1/clients/", headers=auth_headers)
    assert listed.status_code == 200
    assert all(item["id"] != client_id for item in listed.json()["data"]["items"])

    fetched = await client.get(f"/api/v1/clients/{client_id}", headers=auth_headers)
    assert fetched.status_code == 404

    deleted = await client.delete(f"/api/v1/clients/{client_id}", headers=auth_headers)
    assert deleted.status_code == 404


@pytest.mark.asyncio
async def test_fleet_vehicles_are_isolated_between_companies(
    client,
    auth_headers,
    other_auth_headers,
):
    created = await client.post(
        "/api/v1/fleet/vehicles",
        json={
            "plate_number": "OTHER-001",
            "brand": "Tenant",
            "model": "Isolation",
            "location_name": "თბილისი, საქართველო",
            "latitude": 41.7151,
            "longitude": 44.8271,
        },
        headers=other_auth_headers,
    )
    assert created.status_code == 201
    vehicle_id = created.json()["data"]["id"]

    listed = await client.get("/api/v1/fleet/vehicles", headers=auth_headers)
    assert listed.status_code == 200
    assert all(item["id"] != vehicle_id for item in listed.json()["data"])

    fetched = await client.get(
        f"/api/v1/fleet/vehicles/{vehicle_id}",
        headers=auth_headers,
    )
    assert fetched.status_code == 404

    updated = await client.put(
        f"/api/v1/fleet/vehicles/{vehicle_id}",
        json={"location_name": "ბათუმი, საქართველო", "latitude": 41.6168, "longitude": 41.6367},
        headers=auth_headers,
    )
    assert updated.status_code == 404

    deleted = await client.delete(
        f"/api/v1/fleet/vehicles/{vehicle_id}",
        headers=auth_headers,
    )
    assert deleted.status_code == 404


@pytest.mark.asyncio
async def test_expense_rejects_other_company_category(
    client,
    auth_headers,
    other_auth_headers,
):
    category_response = await client.post(
        "/api/v1/expenses/categories",
        json={"name": "Other Tenant Category"},
        headers=other_auth_headers,
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["data"]["id"]

    response = await client.post(
        "/api/v1/expenses/",
        json={
            "category_id": category_id,
            "expense_date": date.today().isoformat(),
            "description": "Cross-tenant category must be rejected",
            "amount": "10.00",
            "currency": "GEL",
        },
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_analytic_entry_rejects_other_company_gl_account(
    client,
    auth_headers,
    other_auth_headers,
):
    analytic_response = await client.post(
        "/api/v1/analytic/accounts",
        json={"code": "MAIN-CC", "name": "Main Cost Center"},
        headers=auth_headers,
    )
    assert analytic_response.status_code == 201
    analytic_account_id = analytic_response.json()["data"]["id"]

    gl_response = await client.post(
        "/api/v1/gl/accounts/",
        json={
            "code": "OTHER-GL-001",
            "name": "Other Tenant GL",
            "account_type": "expense",
        },
        headers=other_auth_headers,
    )
    assert gl_response.status_code == 200
    gl_account_id = gl_response.json()["data"]["id"]

    response = await client.post(
        "/api/v1/analytic/entries",
        json={
            "analytic_account_id": analytic_account_id,
            "gl_account_id": gl_account_id,
            "entry_date": date.today().isoformat(),
            "description": "Cross-tenant GL must be rejected",
            "amount": "10.00",
            "direction": "expense",
        },
        headers=auth_headers,
    )

    assert response.status_code == 404

import pytest
from sqlalchemy import select

from app.models.client import Client
from app.models.company import Company
from app.models.product import Product


@pytest.mark.asyncio
async def test_client_create_persists_vat_and_primary_contact_and_interaction(
    client, auth_headers, test_admin
):
    create_response = await client.post(
        "/api/v1/clients/",
        headers=auth_headers,
        json={
            "client_type": "legal",
            "name": "შპს კონტრაქტის ტესტი",
            "identification_code": "P0-CLIENT-001",
            "is_vat_payer": False,
            "phone": "+995555123456",
            "email": "contact@example.ge",
            "address": "თბილისი",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["is_vat_payer"] is False
    assert created["contacts"][0]["phone"] == "+995555123456"
    assert created["contacts"][0]["email"] == "contact@example.ge"
    assert created["contacts"][0]["is_primary"] is True

    detail_response = await client.get(
        f"/api/v1/clients/{created['id']}", headers=auth_headers
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["is_vat_payer"] is False
    assert detail["contacts"][0]["phone"] == "+995555123456"

    update_response = await client.patch(
        f"/api/v1/clients/{created['id']}",
        headers=auth_headers,
        json={
            "is_vat_payer": True,
            "phone": "+995555654321",
            "email": "updated@example.ge",
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["is_vat_payer"] is True
    assert updated["phone"] == "+995555654321"
    assert updated["email"] == "updated@example.ge"

    interaction_response = await client.post(
        f"/api/v1/clients/{created['id']}/interactions",
        headers=auth_headers,
        json={"type": "call", "description": "პირველი ზარი"},
    )
    assert interaction_response.status_code == 200
    interaction = interaction_response.json()["data"]
    assert interaction["created_by"] == str(test_admin.id)


@pytest.mark.asyncio
async def test_product_categories_static_route_is_reachable(client, auth_headers):
    response = await client.get("/api/v1/products/categories/", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_malformed_excel_import_returns_400(client, auth_headers):
    response = await client.post(
        "/api/v1/import/clients",
        files={
            "file": (
                "malformed.xlsx",
                b"not-an-excel-file",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Excel" in response.json()["detail"]


@pytest.mark.asyncio
async def test_order_rejects_product_from_another_company(
    client, auth_headers, db_session, test_company, test_admin
):
    second_company = Company(
        name="Other Company",
        identification_code="OTHER-001",
        vat_status=True,
        currency="GEL",
    )
    db_session.add(second_company)
    await db_session.flush()

    own_client = Client(
        company_id=test_company.id,
        name="Own Client",
        client_type="legal",
        identification_code="OWN-CLIENT-001",
        vat_status=True,
        status="active",
        created_by=test_admin.id,
    )
    foreign_product = Product(
        company_id=second_company.id,
        sku="FOREIGN-001",
        name="Foreign Product",
        sale_price=100,
        purchase_price=80,
        unit="ცალი",
        min_stock=0,
        current_stock=10,
    )
    db_session.add_all([own_client, foreign_product])
    await db_session.commit()
    await db_session.refresh(own_client)
    await db_session.refresh(foreign_product)

    response = await client.post(
        "/api/v1/orders/",
        headers=auth_headers,
        json={
            "client_id": str(own_client.id),
            "items": [
                {
                    "product_id": str(foreign_product.id),
                    "product_name": foreign_product.name,
                    "quantity": 2,
                    "unit_price": 100,
                    "discount_percent": 0,
                }
            ],
            "is_vat_payer": True,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "პროდუქტი არ მოიძებნა"

    refreshed_stock = (
        await db_session.execute(
            select(Product.current_stock).where(Product.id == foreign_product.id)
        )
    ).scalar_one()
    assert float(refreshed_stock) == 10

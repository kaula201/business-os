import pytest
from sqlalchemy import select

from app.models.product import Product


async def _make_product(db_session, company_id):
    product = Product(
        company_id=company_id,
        name="QC Widget",
        sku="QC-001",
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


async def test_quality_check_crud(client, auth_headers, db_session, test_company, test_admin):
    product = await _make_product(db_session, test_company.id)

    # create
    r = await client.post(
        "/api/v1/quality-control/",
        headers=auth_headers,
        json={
            "product_id": str(product.id),
            "checked_by": str(test_admin.id),
            "status": "pass",
            "notes": "All good",
        },
    )
    assert r.status_code == 201, r.text
    check = r.json()["data"]
    assert check["status"] == "pass"
    assert check["notes"] == "All good"
    assert check["checked_by"] == str(test_admin.id)
    cid = check["id"]

    # list
    r = await client.get("/api/v1/quality-control/", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 1

    # filter by product and status
    r = await client.get(f"/api/v1/quality-control/?product_id={product.id}&status=pass", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 1

    # get
    r = await client.get(f"/api/v1/quality-control/{cid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["id"] == cid

    # update
    r = await client.put(
        f"/api/v1/quality-control/{cid}",
        headers=auth_headers,
        json={"status": "fail", "notes": "Found defect"},
    )
    assert r.status_code == 200, r.text
    updated = r.json()["data"]
    assert updated["status"] == "fail"
    assert updated["notes"] == "Found defect"

    # delete
    r = await client.delete(f"/api/v1/quality-control/{cid}", headers=auth_headers)
    assert r.status_code == 200
    r = await client.get(f"/api/v1/quality-control/{cid}", headers=auth_headers)
    assert r.status_code == 404


async def test_quality_check_requires_auth(client):
    r = await client.get("/api/v1/quality-control/")
    assert r.status_code == 401

"""Vendor portal users CRUD + supplier self-service summary."""
import uuid

import pytest
from sqlalchemy import select

from app.models.vendor_portal import VendorPortalUser
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _create_supplier(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/suppliers/", json={
        "name": f"VP Supplier {suffix}", "code": f"VPS-{suffix}",
        "identification_code": f"VPID-{suffix}", "is_vat_payer": True,
        "email": f"vendor-{suffix}@example.com",
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_product(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/products/", json={
        "sku": f"VPP-{suffix}", "name": f"VP Product {suffix}", "sale_price": 10,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def test_vendor_portal_user_crud(client, auth_headers, test_company, db_session):
    supplier = await _create_supplier(client, auth_headers, "A")

    created = await client.post("/api/v1/vendor-portal/", json={
        "supplier_id": supplier["id"], "email": "portal-a@example.com",
        "display_name": "Portal User A",
    }, headers=auth_headers)
    assert created.status_code in (200, 201), created.text
    user_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "active"

    listed = await client.get("/api/v1/vendor-portal/", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    assert any(u["id"] == user_id for u in listed.json()["data"]["items"])

    updated = await client.patch(f"/api/v1/vendor-portal/{user_id}", json={"status": "disabled"}, headers=auth_headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["status"] == "disabled"

    deleted = await client.delete(f"/api/v1/vendor-portal/{user_id}", headers=auth_headers)
    assert deleted.status_code == 200, deleted.text

    # supplier must belong to the same company
    other = await client.post("/api/v1/vendor-portal/", json={
        "supplier_id": str(uuid.uuid4()), "email": "x@example.com", "display_name": "X",
    }, headers=auth_headers)
    assert other.status_code == 404, other.text


async def test_vendor_portal_supplier_summary(client, auth_headers, test_company, db_session):
    supplier = await _create_supplier(client, auth_headers, "B")
    product = await _create_product(client, auth_headers, "B")

    # RFQ addressed to this supplier
    rfq = await client.post("/api/v1/procurement/rfqs", json={
        "title": "VP RFQ", "supplier_id": supplier["id"],
        "lines": [{"product_id": product["id"], "quantity": 3, "expected_price": 15}],
    }, headers=auth_headers)
    assert rfq.status_code == 201, rfq.text

    # price list for this supplier
    pl = await client.post("/api/v1/procurement/price-lists", json={
        "supplier_id": supplier["id"], "product_id": product["id"], "price": 12.5,
    }, headers=auth_headers)
    assert pl.status_code in (200, 201), pl.text

    summary = await client.get(f"/api/v1/vendor-portal/suppliers/{supplier['id']}/summary", headers=auth_headers)
    assert summary.status_code == 200, summary.text
    data = summary.json()["data"]
    assert data["counts"]["rfqs"] == 1
    assert data["counts"]["price_lists"] == 1
    assert data["rfqs"][0]["rfq_number"].startswith("RFQ-")
    assert data["price_lists"][0]["price"] == 12.5

    # unknown supplier -> 404
    missing = await client.get(f"/api/v1/vendor-portal/suppliers/{uuid.uuid4()}/summary", headers=auth_headers)
    assert missing.status_code == 404, missing.text

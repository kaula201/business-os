"""Vendor self-service auth: login, me, dashboard."""
import uuid

import pytest
from sqlalchemy import select

from app.models.vendor_portal import VendorPortalUser
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _create_supplier(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/suppliers/", json={
        "name": f"VA Supplier {suffix}", "code": f"VAS-{suffix}",
        "identification_code": f"VAID-{suffix}", "is_vat_payer": True,
        "email": f"va-vendor-{suffix}@example.com",
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_product(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/products/", json={
        "sku": f"VAP-{suffix}", "name": f"VA Product {suffix}", "sale_price": 10,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def test_vendor_login_me_dashboard(client, auth_headers, test_company, db_session):
    supplier = await _create_supplier(client, auth_headers, "A")
    product = await _create_product(client, auth_headers, "A")

    # create portal user with password
    created = await client.post("/api/v1/vendor-portal/", json={
        "supplier_id": supplier["id"], "email": "va-portal@example.com",
        "display_name": "VA Portal", "password": "secret123",
    }, headers=auth_headers)
    assert created.status_code in (200, 201), created.text

    # RFQ addressed to this supplier so the dashboard has data
    rfq = await client.post("/api/v1/procurement/rfqs", json={
        "title": "VA RFQ", "supplier_id": supplier["id"],
        "lines": [{"product_id": product["id"], "quantity": 2, "expected_price": 9}],
    }, headers=auth_headers)
    assert rfq.status_code == 201, rfq.text

    # wrong password -> 401
    bad = await client.post("/api/v1/vendor-auth/login", json={
        "email": "va-portal@example.com", "password": "wrongpass",
    })
    assert bad.status_code == 401, bad.text

    # correct login
    login = await client.post("/api/v1/vendor-auth/login", json={
        "email": "va-portal@example.com", "password": "secret123",
    })
    assert login.status_code == 200, login.text
    data = login.json()["data"]
    token = data["access_token"]
    assert data["user"]["supplier_name"] == "VA Supplier A"
    assert data["user"]["status"] == "active"

    vendor_headers = {"Authorization": f"Bearer {token}"}

    # token in the query string is not accepted
    leaked = await client.get("/api/v1/vendor-auth/me", params={"token": token})
    assert leaked.status_code == 401, leaked.text

    # me
    me = await client.get("/api/v1/vendor-auth/me", headers=vendor_headers)
    assert me.status_code == 200, me.text
    assert me.json()["data"]["email"] == "va-portal@example.com"

    # dashboard shows the RFQ
    dash = await client.get("/api/v1/vendor-auth/dashboard", headers=vendor_headers)
    assert dash.status_code == 200, dash.text
    d = dash.json()["data"]
    assert d["counts"]["rfqs"] == 1
    assert d["rfqs"][0]["rfq_number"].startswith("RFQ-")

    # invalid token -> 401
    bad_me = await client.get("/api/v1/vendor-auth/me", headers={"Authorization": "Bearer garbage"})
    assert bad_me.status_code == 401, bad_me.text


async def test_vendor_login_disabled_account(client, auth_headers, test_company, db_session):
    supplier = await _create_supplier(client, auth_headers, "B")
    created = await client.post("/api/v1/vendor-portal/", json={
        "supplier_id": supplier["id"], "email": "va-disabled@example.com",
        "display_name": "VA Disabled", "password": "secret123",
    }, headers=auth_headers)
    assert created.status_code in (200, 201), created.text
    user_id = created.json()["data"]["id"]

    # disable the account
    disabled = await client.patch(f"/api/v1/vendor-portal/{user_id}", json={"status": "disabled"}, headers=auth_headers)
    assert disabled.status_code == 200, disabled.text

    login = await client.post("/api/v1/vendor-auth/login", json={
        "email": "va-disabled@example.com", "password": "secret123",
    })
    assert login.status_code == 403, login.text

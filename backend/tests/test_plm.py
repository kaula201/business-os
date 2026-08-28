"""PLM — product versions, engineering changes (ECO), lifecycle stages."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _seed_product(client, auth_headers) -> str:
    p = await client.post("/api/v1/products/", json={
        "name": f"PLM-{uuid.uuid4().hex[:6]}", "sku": f"PLM-{uuid.uuid4().hex[:6]}",
        "sale_price": 50, "purchase_price": 20,
    }, headers=auth_headers)
    assert p.status_code in (200, 201), p.text
    return p.json()["data"]["id"]


async def test_product_versions(client, auth_headers):
    pid = await _seed_product(client, auth_headers)
    v1 = await client.post(f"/api/v1/plm/products/{pid}/versions", json={"version": "v1.0", "notes": "პირველი"}, headers=auth_headers)
    assert v1.status_code == 201, v1.text
    v2 = await client.post(f"/api/v1/plm/products/{pid}/versions", json={"version": "v1.1", "notes": "გაუმჯობესებული"}, headers=auth_headers)
    assert v2.status_code == 201, v2.text
    assert v2.json()["data"]["revision"] == 2

    lst = await client.get(f"/api/v1/plm/products/{pid}/versions", headers=auth_headers)
    assert lst.status_code == 200
    versions = lst.json()["data"]
    assert len(versions) == 2
    assert versions[0]["is_current"] is True  # newest first


async def test_engineering_change_workflow(client, auth_headers):
    pid = await _seed_product(client, auth_headers)
    e = await client.post("/api/v1/plm/engineering-changes", json={
        "product_id": pid, "title": "მასალის შეცვლა", "change_type": "material", "priority": "high",
    }, headers=auth_headers)
    assert e.status_code == 201, e.text
    eco_id = e.json()["data"]["id"]
    assert e.json()["data"]["eco_number"].startswith("ECO-")

    ap = await client.patch(f"/api/v1/plm/engineering-changes/{eco_id}", json={"status": "approved"}, headers=auth_headers)
    assert ap.status_code == 200, ap.text
    assert ap.json()["data"]["status"] == "approved"

    lst = await client.get("/api/v1/plm/engineering-changes?status=approved", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1


async def test_product_lifecycle(client, auth_headers):
    pid = await _seed_product(client, auth_headers)
    lc = await client.put(f"/api/v1/plm/products/{pid}/lifecycle", json={"stage": "production"}, headers=auth_headers)
    assert lc.status_code == 200, lc.text
    assert lc.json()["data"]["stage"] == "production"

    got = await client.get(f"/api/v1/plm/products/{pid}/lifecycle", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["data"]["stage"] == "production"

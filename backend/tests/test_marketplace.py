"""Marketplace — catalog, publish, install/uninstall, config, my-apps."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _publish_app(client, auth_headers, **overrides) -> str:
    payload = {
        "name": f"App-{uuid.uuid4().hex[:4]}",
        "category": "sales",
        "price": 0,
        "permissions": ["clients", "orders"],
        "config_schema": {"type": "object", "properties": {"api_key": {"type": "string"}}},
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/marketplace/apps", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def test_marketplace_publish_and_catalog(client, auth_headers):
    app_id = await _publish_app(client, auth_headers)

    catalog = await client.get("/api/v1/marketplace/apps", headers=auth_headers)
    assert catalog.status_code == 200, catalog.text
    data = catalog.json()["data"]
    assert data["total"] >= 1
    item = next((a for a in data["items"] if a["id"] == app_id), None)
    assert item is not None
    assert item["installed"] is False
    assert item["permissions"] == ["clients", "orders"]

    detail = await client.get(f"/api/v1/marketplace/apps/{app_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["config_schema"] is not None


async def test_install_uninstall_and_config(client, auth_headers):
    app_id = await _publish_app(client, auth_headers)

    inst = await client.post(f"/api/v1/marketplace/apps/{app_id}/install", json={
        "config": {"api_key": "sk-test-123"},
    }, headers=auth_headers)
    assert inst.status_code == 200, inst.text
    assert inst.json()["data"]["status"] == "installed"

    mine = await client.get("/api/v1/marketplace/my-apps", headers=auth_headers)
    assert mine.status_code == 200, mine.text
    apps = mine.json()["data"]
    assert len(apps) == 1
    assert apps[0]["config"]["api_key"] == "sk-test-123"

    # catalog now shows installed
    catalog = await client.get("/api/v1/marketplace/apps", headers=auth_headers)
    item = next((a for a in catalog.json()["data"]["items"] if a["id"] == app_id), None)
    assert item["installed"] is True

    # update config
    cfg = await client.patch(f"/api/v1/marketplace/apps/{app_id}/config", json={
        "config": {"api_key": "sk-new"},
    }, headers=auth_headers)
    assert cfg.status_code == 200, cfg.text
    mine2 = await client.get("/api/v1/marketplace/my-apps", headers=auth_headers)
    assert mine2.json()["data"][0]["config"]["api_key"] == "sk-new"

    # uninstall
    un = await client.post(f"/api/v1/marketplace/apps/{app_id}/uninstall", headers=auth_headers)
    assert un.status_code == 200, un.text
    mine3 = await client.get("/api/v1/marketplace/my-apps", headers=auth_headers)
    assert len(mine3.json()["data"]) == 0


async def test_marketplace_tenant_isolation(client, auth_headers, test_company):
    app_id = await _publish_app(client, auth_headers)
    await client.post(f"/api/v1/marketplace/apps/{app_id}/install", headers=auth_headers)

    # another company (employee fixture) must not see the installation
    from tests.conftest import TestSessionLocal
    from app.models.company import Company
    from app.models.user import User
    from app.core.security import hash_password
    from sqlalchemy import select

    async with TestSessionLocal() as session:
        other = Company(name="Other Co", identification_code="OTH-1", vat_status=False, currency="GEL")
        session.add(other)
        await session.flush()
        u = User(company_id=other.id, email="other@test.ge",
                 hashed_password=hash_password("admin123"), full_name="Other",
                 role=User.Role.ADMIN, is_active=True)
        session.add(u)
        await session.commit()

    login = await client.post("/api/v1/auth/login", json={"email": "other@test.ge", "password": "admin123"})
    other_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    mine = await client.get("/api/v1/marketplace/my-apps", headers=other_headers)
    assert mine.status_code == 200
    assert len(mine.json()["data"]) == 0

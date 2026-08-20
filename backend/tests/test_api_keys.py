"""API keys — Odoo JSON-2 API style: create, X-API-Key auth, rotation, revocation, bot users."""
import pytest
from sqlalchemy import select

from app.models.integration import ApiKey
from app.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_api_key_lifecycle(client, auth_headers, test_company, db_session):
    # create key
    resp = await client.post("/api/v1/api-keys/", json={"name": "Integration", "scopes": "pos,projects", "ttl_days": 30}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    raw_key = data["key"]
    key_id = data["id"]
    assert raw_key.startswith("bos_")

    # use the key via X-API-Key header → list projects (any endpoint)
    resp = await client.get("/api/v1/projects/", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200, resp.text

    # last_used_at updated
    async with TestSessionLocal() as s:
        key = (await s.execute(select(ApiKey).where(ApiKey.id == key_id))).scalar_one()
        assert key.last_used_at is not None

    # rotate → old key invalid, new key works
    resp = await client.post(f"/api/v1/api-keys/{key_id}/rotate", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    new_key = resp.json()["data"]["key"]
    new_key_id = resp.json()["data"]["id"]

    resp = await client.get("/api/v1/projects/", headers={"X-API-Key": raw_key})
    assert resp.status_code == 401, resp.text  # old key revoked
    resp = await client.get("/api/v1/projects/", headers={"X-API-Key": new_key})
    assert resp.status_code == 200, resp.text

    # revoke the NEW key
    resp = await client.post(f"/api/v1/api-keys/{new_key_id}/revoke", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.get("/api/v1/projects/", headers={"X-API-Key": new_key})
    assert resp.status_code == 401, resp.text


async def test_bot_user(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/api-keys/bot-users", json={
        "email": "bot@demo.ge", "name": "POS Bot",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    bot_id = resp.json()["data"]["id"]

    async with TestSessionLocal() as s:
        bot = (await s.execute(select(User).where(User.id == bot_id))).scalar_one()
        assert bot.email == "bot@demo.ge"
        assert bot.is_active

    # duplicate → 409
    resp = await client.post("/api/v1/api-keys/bot-users", json={
        "email": "bot@demo.ge", "name": "POS Bot 2",
    }, headers=auth_headers)
    assert resp.status_code == 409, resp.text

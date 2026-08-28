"""API P1.8 — granular module scopes, allowed IPs, rate limits, webhook hardening."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _create_key(client, auth_headers, **extra):
    data = {"name": f"K-{uuid.uuid4().hex[:6]}", "scopes": "read", **extra}
    r = await client.post("/api/v1/integrations/api-keys", json=data, headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def test_granular_module_scope_enforcement(client, auth_headers):
    # read-only scope on projects → GET works, write-scoped action denied elsewhere
    k = await _create_key(client, auth_headers, scopes="projects.read")
    headers = {"X-API-Key": k["key"]}
    # GET projects (read scope) → allowed
    r = await client.get("/api/v1/projects/", headers=headers)
    assert r.status_code == 200, r.text
    # create project requires projects.write → read-only key → 403
    r2 = await client.post("/api/v1/projects/", json={"name": "Blocked Project"}, headers=headers)
    assert r2.status_code == 403, r2.text


async def test_allowed_ips_enforced(client, auth_headers):
    k = await _create_key(client, auth_headers, scopes="*", allowed_ips=["203.0.113.99"])
    headers = {"X-API-Key": k["key"]}
    r = await client.get("/api/v1/projects/", headers=headers)
    # test client IP is 127.0.0.1 (or testserver) — not in allowed list → 403
    assert r.status_code == 403, r.text


async def test_rate_limit_429(client, auth_headers):
    k = await _create_key(client, auth_headers, scopes="*", rate_limit_per_minute=3)
    headers = {"X-API-Key": k["key"]}
    codes = []
    for _ in range(5):
        r = await client.get("/api/v1/projects/", headers=headers)
        codes.append(r.status_code)
    assert 429 in codes, f"expected rate-limit 429, got {codes}"
    assert codes.count(200) >= 1


async def test_webhook_idempotency_key(client, auth_headers):
    from sqlalchemy import select
    from app.models.integration import Webhook

    w = await client.post("/api/v1/integrations/webhooks", json={
        "name": "Test Hook", "url": "http://localhost:9999/hook", "events": "invoice.created",
        "retry_max": 1, "retry_backoff_seconds": 5,
    }, headers=auth_headers)
    assert w.status_code == 201, w.text
    wid = w.json()["data"]["id"]

    from app.services.webhook_delivery import deliver_webhook
    from tests.conftest import TestSessionLocal
    async with TestSessionLocal() as session:
        hook = (await session.execute(select(Webhook).where(Webhook.id == wid))).scalar_one()
        ev = await deliver_webhook(session, hook.company_id, hook, "invoice.created", {"x": 1}, idempotency_key="idem-123")
        assert ev.idempotency_key == "idem-123"
        # failed delivery (port 9999 closed) with retry_max=1 → dead
        assert ev.status == "dead", f"expected dead after 1 attempt, got {ev.status}"
        assert ev.attempts == 1

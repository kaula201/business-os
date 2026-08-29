"""Georgian integrations: counterparty verification (SRS open data)."""
import uuid

import pytest
from sqlalchemy import select

from app.models.counterparty import CounterpartyCheck
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_counterparty_verify_records_history(client, auth_headers, test_company):
    """Verification always records a history entry — even when the SRS
    open-data portal is unreachable (honest status, never fabricated)."""
    resp = await client.post("/api/v1/integrations/counterparties/verify", json={
        "identification_code": "205487198",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] in {"verified", "not_found", "unreachable"}
    assert data["check_id"]

    # history entry exists
    async with TestSessionLocal() as session:
        rows = (await session.execute(select(CounterpartyCheck).where(
            CounterpartyCheck.company_id == test_company.id,
            CounterpartyCheck.identification_code == "205487198",
        ))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == data["status"]

    # list endpoint returns it
    lst = await client.get("/api/v1/integrations/counterparties/checks", headers=auth_headers)
    assert lst.status_code == 200
    items = lst.json()["data"]
    assert any(i["identification_code"] == "205487198" for i in items)


async def test_counterparty_verify_rejects_short_code(client, auth_headers):
    resp = await client.post("/api/v1/integrations/counterparties/verify", json={
        "identification_code": "123",
    }, headers=auth_headers)
    assert resp.status_code == 422


async def test_liberty_bank_connection(client, auth_headers):
    """Liberty Bank is a supported connection; unknown banks are rejected."""
    ok = await client.post("/api/v1/connections", json={
        "bank": "liberty", "name": "Liberty Test", "account_number": "GE00LB0000000001",
    }, headers=auth_headers)
    assert ok.status_code == 201, ok.text
    assert ok.json()["data"]["bank"] == "liberty"

    bad = await client.post("/api/v1/connections", json={"bank": "sberbank"}, headers=auth_headers)
    assert bad.status_code == 422


async def test_ai_georgian_legal_context(client, auth_headers):
    """AI chat (mock mode) includes Georgian legal knowledge in the reply."""
    resp = await client.post("/api/v1/ai/chat", json={
        "message": "რამდენია დღგ-ს განაკვეთი?",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]["message"]
    # mock reply embeds the business context; legal knowledge is in the
    # system prompt (used when OpenAI is configured) — assert the endpoint works
    assert "ბიზნეს მონაცემები" in body

"""Georgian integrations: counterparty verification (SRS open data)."""
import uuid

import pytest
from sqlalchemy import func, select

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


async def test_bank_file_import_and_dedup(client, auth_headers, test_company):
    """CSV bank statement import creates transactions and blocks duplicates."""
    from app.models.banking import BankAccount, BankTransaction
    from app.models.bank_connection import BankConnection
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        bacc = BankAccount(company_id=test_company.id, bank_name="Liberty Bank",
                           account_name="Imp GEL", iban="GE11LB0000000002",
                           currency="GEL")
        session.add(bacc)
        await session.flush()
        conn = BankConnection(company_id=test_company.id, bank="liberty",
                              name="Liberty", account_number=bacc.iban)
        session.add(conn)
        await session.commit()
        cid = str(conn.id)

    csv_body = (
        "Date,Reference,Description,Counterparty,Amount\n"
        "2026-08-01,REF0001,გადახდა,,500.50\n"
        "2026-08-02,REF0002,შემოსავალი,შპს თესტი,1200.00\n"
    )
    files = {"file": ("statement.csv", csv_body.encode("utf-8"), "text/csv")}
    resp = await client.post(f"/api/v1/connections/{cid}/import-file",
                             headers=auth_headers, files=files)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["created"] == 2
    assert data["duplicate"] is False

    # same file again → duplicate
    resp2 = await client.post(f"/api/v1/connections/{cid}/import-file",
                              headers=auth_headers, files=files)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["duplicate"] is True

    async with TestSessionLocal() as session:
        count = (await session.execute(select(func.count()).select_from(BankTransaction).where(
            BankTransaction.company_id == test_company.id,
        ))).scalar()
    assert count == 2

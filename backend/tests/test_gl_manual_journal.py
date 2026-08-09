"""Tests for manual journal entry workflow (double-entry validation, tenant scoping, numbering)."""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient

from app.models.company import Company
from app.models.gl import GLAccount
from app.services.gl_posting import seed_default_accounts
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed(client: AsyncClient, auth_headers, test_company) -> dict[str, str]:
    """Seed default COA and return {code: account_id}."""
    async with TestSessionLocal() as session:
        await seed_default_accounts(session, test_company.id)
        await session.commit()
    resp = await client.get("/api/v1/gl/accounts/", headers=auth_headers, params={"page_size": 200})
    assert resp.status_code == 200
    return {a["code"]: a["id"] for a in resp.json()["data"]["items"]}


async def test_create_manual_entry_balanced(client: AsyncClient, auth_headers, test_company):
    acc = await _seed(client, auth_headers, test_company)
    resp = await client.post("/api/v1/gl/journal-entries/", json={
        "entry_date": "2026-08-01",
        "description": "ხელით ჩანაწერი — ბანკი → ხარჯი",
        "lines": [
            {"gl_account_id": acc["5100"], "debit_amount": 150.00, "credit_amount": 0, "description": "ხარჯი"},
            {"gl_account_id": acc["1410"], "debit_amount": 0, "credit_amount": 150.00, "description": "ბანკი"},
        ],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["entry_number"].startswith("JE-20260801-")
    assert data["reference_type"] == "manual"
    assert len(data["lines"]) == 2
    # Entry appears in list
    listing = await client.get("/api/v1/gl/journal-entries/", headers=auth_headers)
    assert listing.status_code == 200
    assert any(e["id"] == data["id"] for e in listing.json()["data"]["items"])


async def test_create_manual_entry_unbalanced_rejected(client: AsyncClient, auth_headers, test_company):
    acc = await _seed(client, auth_headers, test_company)
    resp = await client.post("/api/v1/gl/journal-entries/", json={
        "entry_date": "2026-08-01",
        "description": "არასწორი ბალანსი",
        "lines": [
            {"gl_account_id": acc["5100"], "debit_amount": 100.00, "credit_amount": 0},
            {"gl_account_id": acc["1410"], "debit_amount": 0, "credit_amount": 90.00},
        ],
    }, headers=auth_headers)
    assert resp.status_code == 400
    assert "ბალანსი" in resp.json()["detail"]


async def test_create_manual_entry_cross_tenant_account_rejected(client: AsyncClient, auth_headers, test_company):
    # Account from another company must be rejected
    async with TestSessionLocal() as session:
        other = Company(
            name="სხვა კომპანია",
            identification_code="TEST-999",
            vat_status=False,
            currency="GEL",
        )
        session.add(other)
        await session.flush()
        other_acc = GLAccount(
            company_id=other.id, code="9999", name="სხვისი ანგარიში", account_type="asset",
        )
        session.add(other_acc)
        await session.commit()
        other_acc_id = other_acc.id

    resp = await client.post("/api/v1/gl/journal-entries/", json={
        "entry_date": "2026-08-01",
        "description": "cross-tenant ჩანაწერი",
        "lines": [
            {"gl_account_id": str(other_acc_id), "debit_amount": 50.00, "credit_amount": 0},
            {"gl_account_id": str(uuid.uuid4()), "debit_amount": 0, "credit_amount": 50.00},
        ],
    }, headers=auth_headers)
    assert resp.status_code == 400
    assert "ვერ მოიძებნა" in resp.json()["detail"]


async def test_manual_entry_number_sequence(client: AsyncClient, auth_headers, test_company):
    acc = await _seed(client, auth_headers, test_company)
    numbers = []
    for i in range(2):
        resp = await client.post("/api/v1/gl/journal-entries/", json={
            "entry_date": "2026-08-02",
            "description": f"სექვენცია {i}",
            "lines": [
                {"gl_account_id": acc["5200"], "debit_amount": 10.00, "credit_amount": 0},
                {"gl_account_id": acc["1410"], "debit_amount": 0, "credit_amount": 10.00},
            ],
        }, headers=auth_headers)
        assert resp.status_code == 201
        numbers.append(resp.json()["data"]["entry_number"])
    assert numbers[0] != numbers[1]
    assert numbers[0].endswith("-001")
    assert numbers[1].endswith("-002")

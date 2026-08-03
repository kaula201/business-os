"""Tests for General Ledger foundation: accounts CRUD, journal entries, trial balance."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.services.gl_posting import (
    DEFAULT_ACCOUNTS,
    post_journal_entry,
    seed_default_accounts,
)
from tests.conftest import TEST_DATABASE_URL as TEST_DB_URL, TestSessionLocal

pytestmark = pytest.mark.asyncio

# ── Seed Default Accounts ────────────────────────────────────────────────────


async def test_seed_default_accounts(db_session: AsyncSession, test_company):
    result = await seed_default_accounts(db_session, test_company.id)
    assert len(result) == len(DEFAULT_ACCOUNTS)
    for code, name, _ in DEFAULT_ACCOUNTS:
        assert code in result
    # Idempotent
    result2 = await seed_default_accounts(db_session, test_company.id)
    assert len(result2) == len(DEFAULT_ACCOUNTS)


# ── GL Account CRUD ──────────────────────────────────────────────────────────


async def test_create_account(client: AsyncClient, auth_headers):
    resp = await client.post("/api/v1/gl/accounts/", json={
        "code": "1000", "name": "ნაღდი ფული", "account_type": "asset",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["code"] == "1000"
    assert data["account_type"] == "asset"
    assert data["is_active"] is True


async def test_create_duplicate_code(client: AsyncClient, auth_headers):
    await client.post("/api/v1/gl/accounts/", json={
        "code": "1000", "name": "ნაღდი ფული", "account_type": "asset",
    }, headers=auth_headers)
    resp = await client.post("/api/v1/gl/accounts/", json={
        "code": "1000", "name": "სხვა", "account_type": "asset",
    }, headers=auth_headers)
    assert resp.status_code == 409


async def test_list_accounts(client: AsyncClient, auth_headers, test_company):
    # Seed accounts in a session that commits
    async with TestSessionLocal() as session:
        await seed_default_accounts(session, test_company.id)
        await session.commit()
    resp = await client.get("/api/v1/gl/accounts/", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] > 0


async def test_get_account(client: AsyncClient, auth_headers):
    create = await client.post("/api/v1/gl/accounts/", json={
        "code": "2000", "name": "ვალდებულება", "account_type": "liability",
    }, headers=auth_headers)
    account_id = create.json()["data"]["id"]
    resp = await client.get(f"/api/v1/gl/accounts/{account_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["code"] == "2000"


async def test_update_account(client: AsyncClient, auth_headers):
    create = await client.post("/api/v1/gl/accounts/", json={
        "code": "3000", "name": "კაპიტალი", "account_type": "equity",
    }, headers=auth_headers)
    account_id = create.json()["data"]["id"]
    resp = await client.patch(f"/api/v1/gl/accounts/{account_id}", json={
        "name": "საწესდებო კაპიტალი",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "საწესდებო კაპიტალი"


# ── Journal Entry Posting ─────────────────────────────────────────────────────


async def test_post_journal_entry(db_session: AsyncSession, test_company, test_admin):
    accounts = await seed_default_accounts(db_session, test_company.id)
    entry = await post_journal_entry(
        db_session, test_company.id, test_admin,
        entry_date=date.today(),
        description="სატესტო ჩანაწერი",
        reference_type="test",
        reference_id=uuid.uuid4(),
        lines=[
            ("1300", Decimal("1000"), Decimal("0")),
            ("4100", Decimal("0"), Decimal("1000")),
        ],
    )
    assert entry.entry_number.startswith("GL-")
    assert not entry.is_reversal
    # Verify lines
    lines = (
        await db_session.execute(
            select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id)
        )
    ).scalars().all()
    assert len(lines) == 2
    assert lines[0].debit_amount == Decimal("1000")
    assert lines[1].credit_amount == Decimal("1000")


async def test_unbalanced_entry_raises(db_session: AsyncSession, test_company, test_admin):
    accounts = await seed_default_accounts(db_session, test_company.id)
    with pytest.raises(ValueError, match="Unbalanced"):
        await post_journal_entry(
            db_session, test_company.id, test_admin,
            entry_date=date.today(),
            description="გაუწონასწორებელი",
            reference_type="test",
            reference_id=uuid.uuid4(),
            lines=[
                ("1300", Decimal("1000"), Decimal("0")),
                ("4100", Decimal("0"), Decimal("500")),
            ],
        )


# ── Journal Entry API ─────────────────────────────────────────────────────────


async def test_list_journal_entries(client: AsyncClient, auth_headers, test_company, test_admin):
    async with TestSessionLocal() as session:
        accounts = await seed_default_accounts(session, test_company.id)
        await post_journal_entry(
            session, test_company.id, test_admin,
            entry_date=date.today(),
            description="API ტესტი",
            reference_type="test",
            reference_id=uuid.uuid4(),
            lines=[("1300", Decimal("500"), Decimal("0")), ("4100", Decimal("0"), Decimal("500"))],
        )
        await session.commit()
    resp = await client.get("/api/v1/gl/journal-entries/", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1


async def test_get_journal_entry(client: AsyncClient, auth_headers, test_company, test_admin):
    async with TestSessionLocal() as session:
        accounts = await seed_default_accounts(session, test_company.id)
        entry = await post_journal_entry(
            session, test_company.id, test_admin,
            entry_date=date.today(),
            description="დეტალური ტესტი",
            reference_type="test",
            reference_id=uuid.uuid4(),
            lines=[("1300", Decimal("750"), Decimal("0")), ("4100", Decimal("0"), Decimal("750"))],
        )
        await session.commit()
        entry_id = entry.id
    resp = await client.get(f"/api/v1/gl/journal-entries/{entry_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["description"] == "დეტალური ტესტი"
    assert len(data["lines"]) == 2


# ── Trial Balance ──────────────────────────────────────────────────────────────


async def test_trial_balance(client: AsyncClient, auth_headers, test_company, test_admin):
    async with TestSessionLocal() as session:
        accounts = await seed_default_accounts(session, test_company.id)
        await post_journal_entry(
            session, test_company.id, test_admin,
            entry_date=date.today(),
            description="შემოსავალი",
            reference_type="test",
            reference_id=uuid.uuid4(),
            lines=[("1300", Decimal("2000"), Decimal("0")), ("4100", Decimal("0"), Decimal("2000"))],
        )
        await session.commit()
    resp = await client.get("/api/v1/gl/trial-balance/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["as_of_date"] == date.today().isoformat()
    accounts_list = data["accounts"]
    # Find AR account
    ar = [a for a in accounts_list if a["code"] == "1300"]
    assert len(ar) == 1
    assert ar[0]["balance"] == 2000.0
    # Find income account
    income = [a for a in accounts_list if a["code"] == "4100"]
    assert len(income) == 1
    assert income[0]["balance"] == -2000.0  # credit balance = negative

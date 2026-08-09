"""Tests for recurring journal entries: schedule computation, CRUD, posting."""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient

from app.models.recurring import RecurringJournalEntry
from app.services.gl_posting import seed_default_accounts
from app.services.recurring_entries import compute_next_run, post_due_entries
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed(client: AsyncClient, auth_headers, test_company) -> dict[str, str]:
    async with TestSessionLocal() as session:
        await seed_default_accounts(session, test_company.id)
        await session.commit()
    resp = await client.get("/api/v1/gl/accounts/", headers=auth_headers, params={"page_size": 200})
    return {a["code"]: a["id"] for a in resp.json()["data"]["items"]}


def _make_rec(frequency, interval=1, day_of_week=None, day_of_month=None, start=date(2026, 1, 1)):
    return RecurringJournalEntry(
        company_id=uuid.uuid4(),
        name="t",
        frequency=frequency,
        interval=interval,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        start_date=start,
        next_run_date=start,
        lines=[],
        entry_description="t",
    )


# ── Schedule computation ─────────────────────────────────────────────────────


def test_next_run_daily():
    rec = _make_rec("daily", interval=1)
    assert compute_next_run(rec, date(2026, 1, 1)) == date(2026, 1, 2)


def test_next_run_daily_interval_3():
    rec = _make_rec("daily", interval=3)
    assert compute_next_run(rec, date(2026, 1, 1)) == date(2026, 1, 4)


def test_next_run_weekly_monday():
    # 2026-01-01 is a Thursday (weekday 3)
    rec = _make_rec("weekly", day_of_week=0)  # Monday
    assert compute_next_run(rec, date(2026, 1, 1)) == date(2026, 1, 5)


def test_next_run_monthly_day_15():
    rec = _make_rec("monthly", day_of_month=15)
    assert compute_next_run(rec, date(2026, 1, 1)) == date(2026, 1, 15)
    assert compute_next_run(rec, date(2026, 1, 20)) == date(2026, 2, 15)


def test_next_run_monthly_month_end_clamp():
    # 31-იანი თვეებისთვის clamp: 31 Jan -> 28 Feb
    rec = _make_rec("monthly", day_of_month=31)
    assert compute_next_run(rec, date(2026, 1, 20)) == date(2026, 1, 31)
    assert compute_next_run(rec, date(2026, 1, 31)) == date(2026, 2, 28)


# ── CRUD via API ─────────────────────────────────────────────────────────────


async def test_create_recurring(client: AsyncClient, auth_headers, test_company):
    acc = await _seed(client, auth_headers, test_company)
    resp = await client.post("/api/v1/gl/recurring/", json={
        "name": "ქირა", "frequency": "monthly", "interval": 1, "day_of_month": 5,
        "start_date": "2026-08-05", "entry_description": "ოფისის ქირა",
        "lines": [
            {"gl_account_id": acc["5200"], "debit_amount": 500.00, "credit_amount": 0},
            {"gl_account_id": acc["1410"], "debit_amount": 0, "credit_amount": 500.00},
        ],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["name"] == "ქირა"
    assert data["next_run_date"] == "2026-08-05"
    assert data["total_posted"] == 0


async def test_create_recurring_unbalanced_rejected(client: AsyncClient, auth_headers, test_company):
    acc = await _seed(client, auth_headers, test_company)
    resp = await client.post("/api/v1/gl/recurring/", json={
        "name": "ცუდი", "frequency": "daily", "start_date": "2026-08-01",
        "entry_description": "x",
        "lines": [
            {"gl_account_id": acc["5200"], "debit_amount": 100.00, "credit_amount": 0},
            {"gl_account_id": acc["1410"], "debit_amount": 0, "credit_amount": 90.00},
        ],
    }, headers=auth_headers)
    assert resp.status_code == 400
    assert "ბალანსი" in resp.json()["detail"]


async def test_list_and_delete_recurring(client: AsyncClient, auth_headers, test_company):
    acc = await _seed(client, auth_headers, test_company)
    created = await client.post("/api/v1/gl/recurring/", json={
        "name": "აბონემენტი", "frequency": "weekly", "interval": 1, "day_of_week": 0,
        "start_date": "2026-08-10", "entry_description": "სერვისი",
        "lines": [
            {"gl_account_id": acc["5200"], "debit_amount": 50.00, "credit_amount": 0},
            {"gl_account_id": acc["1410"], "debit_amount": 0, "credit_amount": 50.00},
        ],
    }, headers=auth_headers)
    assert created.status_code == 201
    rec_id = created.json()["data"]["id"]

    listing = await client.get("/api/v1/gl/recurring/", headers=auth_headers)
    assert listing.status_code == 200
    assert any(r["id"] == rec_id for r in listing.json()["data"]["items"])

    deleted = await client.delete(f"/api/v1/gl/recurring/{rec_id}", headers=auth_headers)
    assert deleted.status_code == 200


# ── Posting due entries ──────────────────────────────────────────────────────


async def test_post_due_entries_creates_journal_entries(client: AsyncClient, auth_headers, test_company):
    acc = await _seed(client, auth_headers, test_company)
    created = await client.post("/api/v1/gl/recurring/", json={
        "name": "ყოველდღიური", "frequency": "daily", "interval": 1,
        "start_date": "2026-08-01", "entry_description": "დღიური ხარჯი",
        "lines": [
            {"gl_account_id": acc["5200"], "debit_amount": 10.00, "credit_amount": 0},
            {"gl_account_id": acc["1410"], "debit_amount": 0, "credit_amount": 10.00},
        ],
    }, headers=auth_headers)
    assert created.status_code == 201
    rec_id = created.json()["data"]["id"]

    # Update next_run to the past so it's due
    async with TestSessionLocal() as session:
        rec = (await session.execute(
            __import__("sqlalchemy").select(RecurringJournalEntry).where(RecurringJournalEntry.id == uuid.UUID(rec_id))
        )).scalar_one()
        rec.next_run_date = date(2026, 7, 1)
        await session.commit()

    resp = await client.post("/api/v1/gl/recurring/run", headers=auth_headers)
    assert resp.status_code == 200
    posted = resp.json()["data"]["posted"]
    assert posted == 1

    # Journal entry exists with recurring reference
    entries = await client.get("/api/v1/gl/journal-entries/", headers=auth_headers, params={"reference_type": "recurring"})
    assert entries.status_code == 200
    items = entries.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["entry_number"].startswith("RJE-")

    # Next run advanced
    async with TestSessionLocal() as session:
        rec = (await session.execute(
            __import__("sqlalchemy").select(RecurringJournalEntry).where(RecurringJournalEntry.id == uuid.UUID(rec_id))
        )).scalar_one()
        assert rec.last_run_date == date(2026, 7, 1)
        assert rec.next_run_date == date(2026, 7, 2)
        assert rec.total_posted == 1

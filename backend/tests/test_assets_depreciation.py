"""Asset depreciation: GL posting integration, schedule, bulk run."""
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.models.assets import AssetDepreciation, FixedAsset
from app.models.gl import JournalEntry, JournalEntryLine
from app.models.gl import GLAccount
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _create_asset(client, auth_headers, suffix: str, cost=12000, life=5):
    resp = await client.post("/api/v1/assets/", json={
        "name": f"Depr Asset {suffix}", "asset_type": "equipment",
        "purchase_date": "2026-01-15", "purchase_cost": cost,
        "useful_life_years": life, "depreciation_method": "straight_line",
        "salvage_value": 0,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def test_depreciation_posts_gl_entry(client, auth_headers, test_company, db_session):
    asset = await _create_asset(client, auth_headers, "A", cost=12000, life=5)
    # monthly straight-line: 12000 / (5*12) = 200.00

    run = await client.post(f"/api/v1/assets/{asset['id']}/run-depreciation", headers=auth_headers)
    assert run.status_code == 200, run.text
    data = run.json()["data"]
    assert data["depreciation_amount"] == 200.0
    assert data["new_book_value"] == 11800.0

    # GL entry exists: Dr 5500 200, Cr 1101 200
    async with TestSessionLocal() as s:
        dep = (await s.execute(select(AssetDepreciation).where(AssetDepreciation.asset_id == uuid.UUID(asset["id"])))).scalar_one()
        entry = (await s.execute(select(JournalEntry).where(JournalEntry.reference_id == dep.id, JournalEntry.reference_type == "asset_depreciation"))).scalar_one()
        lines = (await s.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))).scalars().all()
        assert len(lines) == 2
        dr = next(l for l in lines if l.debit_amount > 0)
        cr = next(l for l in lines if l.credit_amount > 0)
        dr_acct = (await s.execute(select(GLAccount).where(GLAccount.id == dr.gl_account_id))).scalar_one()
        cr_acct = (await s.execute(select(GLAccount).where(GLAccount.id == cr.gl_account_id))).scalar_one()
        assert dr_acct.code == "5500"
        assert cr_acct.code == "1101"
        assert float(dr.debit_amount) == 200.0
        assert float(cr.credit_amount) == 200.0


async def test_depreciation_schedule(client, auth_headers, test_company, db_session):
    asset = await _create_asset(client, auth_headers, "B", cost=12000, life=5)
    # 12000 / (5*12) = 200/month → 60 periods

    schedule = await client.get(f"/api/v1/assets/{asset['id']}/schedule", headers=auth_headers)
    assert schedule.status_code == 200, schedule.text
    rows = schedule.json()["data"]
    assert len(rows) == 60
    # first period is the purchase month (no run yet)
    assert rows[0]["period"] == "2026-01"
    assert rows[0]["amount"] == 200.0
    # last period fully depreciates
    assert abs(rows[-1]["accumulated_after"] - 12000.0) < 0.01

    # after a run (uses current date), schedule starts the next month
    run = await client.post(f"/api/v1/assets/{asset['id']}/run-depreciation", headers=auth_headers)
    assert run.status_code == 200, run.text
    schedule2 = await client.get(f"/api/v1/assets/{asset['id']}/schedule", headers=auth_headers)
    rows2 = schedule2.json()["data"]
    assert len(rows2) == 59
    # next month after today (date-agnostic — test was written when today was 2026-08)
    today = date.today()
    y, m = today.year, today.month
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    assert rows2[0]["period"] == f"{ny:04d}-{nm:02d}"


async def test_asset_disposal_posts_gain_loss(client, auth_headers, test_company, db_session):
    # cost 12000, life 5y → 200/month; run 1 depreciation → book 11800
    asset = await _create_asset(client, auth_headers, "D", cost=12000, life=5)
    run = await client.post(f"/api/v1/assets/{asset['id']}/run-depreciation", headers=auth_headers)
    assert run.status_code == 200, run.text
    assert run.json()["data"]["new_book_value"] == 11800.0

    # dispose with proceeds 12000 → gain +200 (Dr 1101 200, Dr 1410 12000, Cr 1100 12000, Cr 4900 200)
    dis = await client.post(f"/api/v1/assets/{asset['id']}/dispose", json={
        "disposal_date": "2026-08-20", "proceeds": 12000,
    }, headers=auth_headers)
    assert dis.status_code == 200, dis.text
    d = dis.json()["data"]
    assert d["book_value"] == 11800.0
    assert d["gain_loss"] == 200.0

    # status disposed
    async with TestSessionLocal() as s:
        a = (await s.execute(select(FixedAsset).where(FixedAsset.id == uuid.UUID(asset["id"])))).scalar_one()
        assert a.status == "disposed"
        assert a.disposal_date == date(2026, 8, 20)
        # GL entry lines
        entry = (await s.execute(select(JournalEntry).where(
            JournalEntry.reference_type == "asset_disposal", JournalEntry.reference_id == uuid.UUID(asset["id"]),
        ))).scalar_one()
        lines = (await s.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))).scalars().all()
        codes = {}
        for l in lines:
            acct = (await s.execute(select(GLAccount).where(GLAccount.id == l.gl_account_id))).scalar_one()
            codes[acct.code] = (float(l.debit_amount), float(l.credit_amount))
        assert codes["1101"] == (200.0, 0.0)      # accumulated write-off
        assert codes["1410"] == (12000.0, 0.0)    # proceeds in bank
        assert codes["1100"] == (0.0, 12000.0)    # asset cost out
        assert codes["4900"] == (0.0, 200.0)      # gain

    # double dispose → 400
    dis2 = await client.post(f"/api/v1/assets/{asset['id']}/dispose", json={"disposal_date": "2026-08-21", "proceeds": 0}, headers=auth_headers)
    assert dis2.status_code == 400, dis2.text


async def test_asset_disposal_loss(client, auth_headers, test_company, db_session):
    asset = await _create_asset(client, auth_headers, "E", cost=12000, life=5)
    run = await client.post(f"/api/v1/assets/{asset['id']}/run-depreciation", headers=auth_headers)
    assert run.status_code == 200, run.text
    # proceeds 5000 → loss -6800 (Dr 1101 200, Dr 1410 5000, Dr 5990 6800, Cr 1100 12000)
    dis = await client.post(f"/api/v1/assets/{asset['id']}/dispose", json={
        "disposal_date": "2026-08-20", "proceeds": 5000,
    }, headers=auth_headers)
    assert dis.status_code == 200, dis.text
    assert dis.json()["data"]["gain_loss"] == -6800.0

    async with TestSessionLocal() as s:
        entry = (await s.execute(select(JournalEntry).where(
            JournalEntry.reference_type == "asset_disposal", JournalEntry.reference_id == uuid.UUID(asset["id"]),
        ))).scalar_one()
        lines = (await s.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))).scalars().all()
        codes = {}
        for l in lines:
            acct = (await s.execute(select(GLAccount).where(GLAccount.id == l.gl_account_id))).scalar_one()
            codes[acct.code] = (float(l.debit_amount), float(l.credit_amount))
        assert codes["5990"] == (6800.0, 0.0)     # loss
        assert codes["1100"] == (0.0, 12000.0)


async def test_run_all_depreciation_idempotent(client, auth_headers, test_company, db_session):
    a1 = await _create_asset(client, auth_headers, "C1", cost=6000, life=5)   # 100/month
    a2 = await _create_asset(client, auth_headers, "C2", cost=12000, life=5)  # 200/month

    run1 = await client.post("/api/v1/assets/run-all-depreciation", headers=auth_headers)
    assert run1.status_code == 200, run1.text
    d1 = run1.json()["data"]
    assert d1["processed"] == 2
    total = sum(i["amount"] for i in d1["items"])
    assert total == 300.0

    # second run same period → both skipped (idempotent)
    run2 = await client.post("/api/v1/assets/run-all-depreciation", headers=auth_headers)
    assert run2.status_code == 200, run2.text
    d2 = run2.json()["data"]
    assert all(i["skipped"] for i in d2["items"])

    # only one GL entry per asset
    async with TestSessionLocal() as s:
        entries = (await s.execute(
            select(JournalEntry).where(JournalEntry.reference_type == "asset_depreciation")
        )).scalars().all()
        assert len(entries) == 2

"""Asset depreciation: GL posting integration, schedule, bulk run."""
import uuid

import pytest
from sqlalchemy import select

from app.models.assets import AssetDepreciation
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

    # after a run (uses current date 2026-08), schedule starts the next month
    run = await client.post(f"/api/v1/assets/{asset['id']}/run-depreciation", headers=auth_headers)
    assert run.status_code == 200, run.text
    schedule2 = await client.get(f"/api/v1/assets/{asset['id']}/schedule", headers=auth_headers)
    rows2 = schedule2.json()["data"]
    assert len(rows2) == 59
    assert rows2[0]["period"] == "2026-09"


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

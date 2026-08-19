"""Deferred schedule cancellation."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.deferred import DeferredRecognition, DeferredSchedule
from app.models.gl import GLAccount
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_account(db, company, code: str, name: str, acct_type: str) -> GLAccount:
    acc = GLAccount(company_id=company.id, code=code, name=name, account_type=acct_type)
    db.add(acc)
    await db.flush()
    return acc


async def _create_schedule(client, auth_headers, test_company, db_session):
    # expense deferral: asset → expense (unique codes, 5200 exists in default COA)
    source = await _make_account(db_session, test_company, "1550", "გადავადებული ხარჯი (ტესტი)", "asset")
    target = await _make_account(db_session, test_company, "5250", "საოპერაციო ხარჯები (ტესტი)", "expense")
    await db_session.commit()

    resp = await client.post("/api/v1/deferred/schedules", json={
        "name": "Cancel Test Schedule",
        "deferral_type": "expense",
        "total_amount": 300.0,
        "start_date": "2026-01-01",
        "periods": 3,
        "source_gl_account_id": str(source.id),
        "recognition_gl_account_id": str(target.id),
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_cancel_schedule_marks_pending_cancelled(client, auth_headers, test_company, db_session):
    data = await _create_schedule(client, auth_headers, test_company, db_session)
    schedule_id = data["id"]
    # 3 periods pending

    # recognize the first period, then cancel the schedule
    first = data["recognitions"][0]
    rec = await client.post(f"/api/v1/deferred/recognitions/{first['id']}/recognize", headers=auth_headers)
    assert rec.status_code == 200, rec.text

    cancel = await client.post(f"/api/v1/deferred/schedules/{schedule_id}/cancel", headers=auth_headers)
    assert cancel.status_code == 200, cancel.text
    cdata = cancel.json()["data"]
    assert cdata["cancelled_periods"] == 2

    async with TestSessionLocal() as s:
        sched = (await s.execute(select(DeferredSchedule).where(DeferredSchedule.id == schedule_id))).scalar_one()
        assert sched.status == "cancelled"
        periods = (await s.execute(select(DeferredRecognition).where(DeferredRecognition.schedule_id == schedule_id))).scalars().all()
        statuses = {p.status for p in periods}
        assert "recognized" in statuses
        assert "cancelled" in statuses
        assert "pending" not in statuses

    # double cancel → 400
    cancel2 = await client.post(f"/api/v1/deferred/schedules/{schedule_id}/cancel", headers=auth_headers)
    assert cancel2.status_code == 400, cancel2.text

"""SaaS tenant billing: plans, entitlement, subscribe, cancel, and TMS limit gating."""
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import delete, select

from app.models.fleet_tms import Driver, Trip
from app.models.saas import TenantPlan, TenantSubscription
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

STARTER_LIMITS = {"max_drivers": 3, "max_vehicles": 5, "max_trips_month": 50,
                  "geocoder": True, "eta": True, "live_map": True}


async def _ensure_plan(client, auth_headers, code="tms_starter", limits=None, amount="49.00"):
    """Create (or reuse) a tenant plan via the admin API — test DB uses create_all, not migrations."""
    r = await client.get("/api/v1/saas/plans", headers=auth_headers)
    plans = r.json()["data"]
    for p in plans:
        if p["code"] == code:
            return p
    r = await client.post("/api/v1/saas/plans", json={
        "code": code, "name": code, "amount": amount, "frequency": "monthly",
        "feature_limits": limits or STARTER_LIMITS,
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]


async def _entitlement(client, auth_headers):
    r = await client.get("/api/v1/saas/entitlement", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _subscribe(client, auth_headers, plan_code, trial_days=14):
    r = await client.post("/api/v1/saas/subscribe", json={
        "plan_code": plan_code, "trial_days": trial_days,
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]


async def _cleanup_saas(company_id):
    async with TestSessionLocal() as s:
        await s.execute(delete(TenantSubscription).where(TenantSubscription.company_id == company_id))
        await s.commit()


async def test_plans_crud_and_list(client, auth_headers):
    plan = await _ensure_plan(client, auth_headers, "tms_starter")
    assert plan["feature_limits"]["max_drivers"] == 3
    assert plan["frequency"] == "monthly"

    r = await client.get("/api/v1/saas/plans", headers=auth_headers)
    codes = {p["code"] for p in r.json()["data"]}
    assert "tms_starter" in codes


async def test_entitlement_unlimited_when_no_subscription(client, auth_headers, test_company):
    await _cleanup_saas(test_company.id)
    d = await _entitlement(client, auth_headers)
    assert d["subscribed"] is False
    assert d["active"] is True  # self-hosted keeps working


async def test_subscribe_and_entitlement(client, auth_headers, test_company):
    await _cleanup_saas(test_company.id)
    await _ensure_plan(client, auth_headers, "tms_starter")
    sub = await _subscribe(client, auth_headers, "tms_starter", trial_days=14)
    assert sub["status"] == "trial"
    assert sub["plan_code"] == "tms_starter"
    assert sub["feature_limits"]["max_drivers"] == 3
    assert sub["trial_ends_at"] == (date.today() + timedelta(days=14)).isoformat()

    d = await _entitlement(client, auth_headers)
    assert d["subscribed"] is True
    assert d["status"] == "trial"
    assert d["active"] is True
    assert d["feature_limits"]["max_drivers"] == 3


async def test_cancel_marks_inactive(client, auth_headers, test_company):
    await _cleanup_saas(test_company.id)
    await _ensure_plan(client, auth_headers, "tms_starter")
    await _subscribe(client, auth_headers, "tms_starter", trial_days=14)
    r = await client.post("/api/v1/saas/cancel", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"

    d = await _entitlement(client, auth_headers)
    assert d["active"] is False
    assert d["status"] == "cancelled"


async def test_tms_trip_blocked_when_inactive(client, auth_headers, test_company):
    await _cleanup_saas(test_company.id)
    await _ensure_plan(client, auth_headers, "tms_starter")
    await _subscribe(client, auth_headers, "tms_starter", trial_days=14)
    await client.post("/api/v1/saas/cancel", headers=auth_headers)

    r = await client.post("/api/v1/fleet/tms/trips", headers=auth_headers, json={
        "trip_number": f"TR-BLOCK-{uuid.uuid4().hex[:6]}",
    })
    assert r.status_code == 402, r.text

    # resubscribe → allowed again
    await _ensure_plan(client, auth_headers, "tms_enterprise", limits={"max_drivers": -1, "max_vehicles": -1, "max_trips_month": -1}, amount="399.00")
    await _subscribe(client, auth_headers, "tms_enterprise", trial_days=14)
    r2 = await client.post("/api/v1/fleet/tms/trips", headers=auth_headers, json={
        "trip_number": f"TR-OK-{uuid.uuid4().hex[:6]}",
    })
    assert r2.status_code == 200, r2.text
    trip_id = r2.json()["data"]["id"]

    async with TestSessionLocal() as s:
        await s.execute(delete(Trip).where(Trip.id == uuid.UUID(trip_id)))
        await s.commit()


async def test_driver_limit_enforced(client, auth_headers, test_company):
    await _cleanup_saas(test_company.id)
    await _ensure_plan(client, auth_headers, "tms_starter")
    await _subscribe(client, auth_headers, "tms_starter", trial_days=14)

    async with TestSessionLocal() as s:
        await s.execute(delete(Driver).where(Driver.company_id == test_company.id))
        await s.commit()

    for i in range(3):
        r = await client.post("/api/v1/fleet/tms/drivers", headers=auth_headers, json={
            "name": f"დრაივერი {i}", "phone": f"+995599{i:06d}",
        })
        assert r.status_code == 201, r.text

    # 4th driver → blocked by starter max_drivers=3
    r = await client.post("/api/v1/fleet/tms/drivers", headers=auth_headers, json={
        "name": "დრაივერი 4", "phone": "+995599999999",
    })
    assert r.status_code == 402, r.text

    async with TestSessionLocal() as s:
        await s.execute(delete(Driver).where(Driver.company_id == test_company.id))
        await s.commit()

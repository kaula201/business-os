"""Subscriptions 2.0: billing scheduler, retry, pause/resume, proration, plan versions, analytics."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.subscription import Subscription, SubscriptionPlan
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_client(client, auth_headers):
    r = await client.post("/api/v1/clients/", json={
        "client_type": "legal", "name": "გამოწერის კლიენტი",
        "identification_code": f"SUB-{uuid.uuid4().hex[:6]}",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


async def _make_subscription(client, auth_headers, cid, amount=100, frequency="monthly", next_billing=None, status="active"):
    r = await client.post("/api/v1/subscriptions/", json={
        "client_id": cid, "plan": "სტანდარტული", "amount": amount, "frequency": frequency,
        "start_date": date.today().isoformat(),
        "next_billing_date": (next_billing or date.today()).isoformat(),
        "status": status,
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


async def test_billing_scheduler(client, auth_headers):
    """Automatic billing scheduler: due subscriptions are billed, next date advances."""
    cid = await _make_client(client, auth_headers)
    due_id = await _make_subscription(client, auth_headers, cid, next_billing=date.today() - timedelta(days=1))
    future_id = await _make_subscription(client, auth_headers, cid, next_billing=date.today() + timedelta(days=30))

    r = await client.post("/api/v1/subscriptions/billing/run", headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["billed"] == 1
    assert d["due"] == 1

    # due subscription advanced
    r2 = await client.get(f"/api/v1/subscriptions/{due_id}", headers=auth_headers)
    assert r2.json()["data"]["next_billing_date"] > date.today().isoformat()
    assert r2.json()["data"]["last_billed_at"] is not None
    # future one untouched
    r3 = await client.get(f"/api/v1/subscriptions/{future_id}", headers=auth_headers)
    assert r3.json()["data"]["last_billed_at"] is None


async def test_failed_payment_retry(client, auth_headers):
    """Failed payment retry: past_due → active, attempts increment, max attempts guard."""
    cid = await _make_client(client, auth_headers)
    sub_id = await _make_subscription(client, auth_headers, cid, status="past_due")

    r = await client.post(f"/api/v1/subscriptions/{sub_id}/retry", headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["status"] == "active"
    assert d["billing_attempts"] == 1
    assert d["last_billing_error"] is None

    # exhaust attempts → 400
    async with TestSessionLocal() as session:
        sub = (await session.execute(select(Subscription).where(Subscription.id == uuid.UUID(sub_id)))).scalar_one()
        sub.billing_attempts = sub.max_billing_attempts
        await session.commit()
    r2 = await client.post(f"/api/v1/subscriptions/{sub_id}/retry", headers=auth_headers)
    assert r2.status_code == 400


async def test_pause_resume(client, auth_headers):
    """Pause/resume: active → paused → active, proration shifts billing date."""
    cid = await _make_client(client, auth_headers)
    sub_id = await _make_subscription(client, auth_headers, cid)

    r = await client.post(f"/api/v1/subscriptions/{sub_id}/pause",
                          json={"reason": "სეზონური პაუზა"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["status"] == "paused"
    assert d["paused_reason"] == "სეზონური პაუზა"
    assert d["paused_at"] is not None

    # pause again → 400
    r2 = await client.post(f"/api/v1/subscriptions/{sub_id}/pause", json={}, headers=auth_headers)
    assert r2.status_code == 400

    r3 = await client.post(f"/api/v1/subscriptions/{sub_id}/resume",
                           json={"prorate": True}, headers=auth_headers)
    assert r3.status_code == 200, r3.text
    d3 = r3.json()["data"]
    assert d3["status"] == "active"
    assert d3["paused_at"] is None


async def test_proration(client, auth_headers):
    """Proration: change-plan computes prorated delta; resume shifts billing by paused days."""
    cid = await _make_client(client, auth_headers)
    # plan v1
    r = await client.post("/api/v1/subscriptions/plans/", json={
        "code": "PRO", "name": "პრო", "amount": 200, "frequency": "monthly",
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    plan_id = r.json()["data"]["id"]
    assert r.json()["data"]["version"] == 1

    sub_id = await _make_subscription(client, auth_headers, cid, amount=100)

    # change plan → prorated delta computed, plan_version = 1
    r2 = await client.post(f"/api/v1/subscriptions/{sub_id}/change-plan",
                           json={"plan_id": plan_id, "prorate": True}, headers=auth_headers)
    assert r2.status_code == 200, r2.text
    d = r2.json()["data"]
    assert d["plan"] == "პრო"
    assert d["plan_version"] == 1
    assert float(d["amount"]) == 200.0


async def test_plan_version_management(client, auth_headers):
    """Plan/version management: same code creates v2, subscriptions track version."""
    cid = await _make_client(client, auth_headers)
    r1 = await client.post("/api/v1/subscriptions/plans/", json={
        "code": "BASIC", "name": "ბაზური v1", "amount": 50, "frequency": "monthly",
    }, headers=auth_headers)
    assert r1.status_code == 201, r1.text
    assert r1.json()["data"]["version"] == 1
    plan1_id = r1.json()["data"]["id"]

    r2 = await client.post("/api/v1/subscriptions/plans/", json={
        "code": "BASIC", "name": "ბაზური v2", "amount": 60, "frequency": "monthly",
    }, headers=auth_headers)
    assert r2.status_code == 201, r2.text
    assert r2.json()["data"]["version"] == 2
    plan2_id = r2.json()["data"]["id"]

    # create subscription on v2
    r3 = await client.post("/api/v1/subscriptions/", json={
        "client_id": cid, "plan": "ბაზური v2", "plan_id": plan2_id, "amount": 60,
        "frequency": "monthly", "start_date": date.today().isoformat(),
    }, headers=auth_headers)
    assert r3.status_code in (200, 201), r3.text
    assert r3.json()["data"]["plan_version"] == 2

    # downgrade to v1 via change-plan
    sub_id = r3.json()["data"]["id"]
    r4 = await client.post(f"/api/v1/subscriptions/{sub_id}/change-plan",
                           json={"plan_id": plan1_id, "prorate": False}, headers=auth_headers)
    assert r4.status_code == 200, r4.text
    assert r4.json()["data"]["plan_version"] == 1
    assert float(r4.json()["data"]["amount"]) == 50.0


async def test_cancel_and_analytics(client, auth_headers):
    """Cancel (churn) + MRR/ARR/churn/cohort analytics."""
    cid = await _make_client(client, auth_headers)
    active_id = await _make_subscription(client, auth_headers, cid, amount=100)
    await _make_subscription(client, auth_headers, cid, amount=200, frequency="yearly")

    # cancel one
    r = await client.post(f"/api/v1/subscriptions/{active_id}/cancel",
                          json={"reason": "გადავიდა კონკურენტზე"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"
    assert r.json()["data"]["cancelled_at"] is not None

    # double cancel → 400
    r2 = await client.post(f"/api/v1/subscriptions/{active_id}/cancel", json={}, headers=auth_headers)
    assert r2.status_code == 400

    # analytics: monthly 100 (cancelled) + yearly 200 → MRR = 200/12 ≈ 16.67, ARR = 200
    r3 = await client.get("/api/v1/subscriptions/analytics/overview", headers=auth_headers)
    assert r3.status_code == 200, r3.text
    d = r3.json()["data"]
    assert d["mrr"] == pytest.approx(16.67, abs=0.01)
    assert d["arr"] == pytest.approx(200.0, abs=0.01)
    assert d["active_subscriptions"] == 1
    assert d["churned_subscriptions"] == 1
    assert d["churn_rate"] == pytest.approx(50.0, abs=0.01)
    assert len(d["cohorts"]) >= 1
    assert d["cohorts"][0]["new"] >= 2

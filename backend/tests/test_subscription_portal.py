"""Tests for subscription renewal and customer portal summary."""
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.client import Client
from app.models.subscription import Subscription
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed_client(test_company) -> str:
    async with TestSessionLocal() as session:
        cust = Client(company_id=test_company.id, name="Sub Client", client_type="legal",
                      identification_code=f"SUB-{uuid.uuid4().hex[:6]}", vat_status=True, status="active")
        session.add(cust)
        await session.commit()
        return str(cust.id)


async def test_subscription_create_sets_next_billing(client, auth_headers, test_company):
    client_id = await _seed_client(test_company)
    resp = await client.post("/api/v1/subscriptions/", json={
        "client_id": client_id, "plan": "პრემიუმი", "amount": 99,
        "frequency": "monthly", "start_date": "2026-08-11", "status": "active",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["next_billing_date"] == "2026-09-11"  # monthly +1 month


async def test_subscription_renew_advances_billing(client, auth_headers, test_company):
    client_id = await _seed_client(test_company)
    created = await client.post("/api/v1/subscriptions/", json={
        "client_id": client_id, "plan": "ბაზური", "amount": 50,
        "frequency": "monthly", "start_date": "2026-08-01", "status": "active",
    }, headers=auth_headers)
    assert created.status_code == 200
    sub_id = created.json()["data"]["id"]
    assert created.json()["data"]["next_billing_date"] == "2026-09-01"

    renewed = await client.post(f"/api/v1/subscriptions/{sub_id}/renew", headers=auth_headers)
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["data"]["next_billing_date"] == "2026-10-01"


async def test_subscription_renew_inactive_rejected(client, auth_headers, test_company):
    client_id = await _seed_client(test_company)
    created = await client.post("/api/v1/subscriptions/", json={
        "client_id": client_id, "plan": "პაუზა", "amount": 10,
        "frequency": "monthly", "start_date": "2026-08-01", "status": "paused",
    }, headers=auth_headers)
    sub_id = created.json()["data"]["id"]
    resp = await client.post(f"/api/v1/subscriptions/{sub_id}/renew", headers=auth_headers)
    assert resp.status_code == 400


async def test_portal_summary_returns_client_picture(client, auth_headers, test_company):
    client_id = await _seed_client(test_company)
    # create portal user
    portal = await client.post("/api/v1/customer-portal/", json={
        "client_id": client_id, "email": f"portal-{uuid.uuid4().hex[:6]}@client.ge",
        "display_name": "კლიენტი",
    }, headers=auth_headers)
    assert portal.status_code in (200, 201), portal.text

    summary = await client.get(f"/api/v1/customer-portal/clients/{client_id}/summary", headers=auth_headers)
    assert summary.status_code == 200, summary.text
    data = summary.json()["data"]
    assert data["client_id"] == client_id
    assert "outstanding_balance" in data
    assert "invoices" in data and "orders" in data

"""Tests for sales teams, targets, and commissions."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.models.sales_team import CommissionAccrual, CommissionRule, SalesTarget, SalesTeam, SalesTeamMember
from app.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _create_sales_user(db_session, company_id: uuid.UUID, email: str) -> User:
    user = User(
        company_id=company_id, email=email,
        hashed_password=hash_password("admin123"),
        full_name="Sales Rep", role=User.Role.MANAGER, is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _create_order(client, auth_headers, test_company, db_session, amount: float = 500.0) -> str:
    from app.models.client import Client
    from app.models.product import Product
    async with TestSessionLocal() as session:
        cust = Client(company_id=test_company.id, name="Sales Cust", client_type="legal",
                      identification_code=f"SC-{uuid.uuid4().hex[:6]}", vat_status=False, status="active")
        prod = Product(company_id=test_company.id, sku=f"SP-{uuid.uuid4().hex[:6]}",
                       name="Sales Prod", sale_price=amount, current_stock=10)
        session.add_all([cust, prod])
        await session.commit()
        cust_id, prod_id = str(cust.id), str(prod.id)
    resp = await client.post("/api/v1/orders/", json={
        "client_id": cust_id,
        "items": [{"product_id": prod_id, "product_name": "Sales Prod", "quantity": 1,
                   "unit_price": amount, "discount_percent": 0}],
        "delivery_address": "Tbilisi", "notes": "comm test",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


# ── Sales teams ──────────────────────────────────────────────────────────────


async def test_team_crud_and_members(client, auth_headers, test_company, db_session):
    sales_user = await _create_sales_user(db_session, test_company.id, f"rep-{uuid.uuid4().hex[:6]}@test.ge")

    created = await client.post("/api/v1/sales/teams/", json={
        "name": "ჩრდილოეთი", "manager_id": str(sales_user.id),
    }, headers=auth_headers)
    assert created.status_code == 201, created.text
    team_id = created.json()["data"]["id"]

    listed = await client.get("/api/v1/sales/teams/", headers=auth_headers)
    assert listed.status_code == 200
    assert any(t["id"] == team_id for t in listed.json()["data"]["items"])

    member = await client.post(f"/api/v1/sales/teams/{team_id}/members",
                               json={"user_id": str(sales_user.id)}, headers=auth_headers)
    assert member.status_code == 201

    detail = await client.get("/api/v1/sales/teams/", headers=auth_headers)
    team = next(t for t in detail.json()["data"]["items"] if t["id"] == team_id)
    assert team["member_count"] == 1

    removed = await client.delete(f"/api/v1/sales/teams/{team_id}/members/{sales_user.id}", headers=auth_headers)
    assert removed.status_code == 200


# ── Sales targets ────────────────────────────────────────────────────────────


async def test_target_create_and_progress(client, auth_headers, test_company):
    created = await client.post("/api/v1/sales/targets/", json={
        "period": "2026-08", "target_amount": 1000,
    }, headers=auth_headers)
    assert created.status_code == 201, created.text
    target_id = created.json()["data"]["id"]

    updated = await client.patch(f"/api/v1/sales/targets/{target_id}",
                                 json={"achieved_amount": 250}, headers=auth_headers)
    assert updated.status_code == 200
    data = updated.json()["data"]
    assert data["achieved_amount"] == 250.0
    assert data["progress_percent"] == 25.0

    listed = await client.get("/api/v1/sales/targets/", params={"period": "2026-08"}, headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()["data"]["items"]) >= 1


# ── Commissions ──────────────────────────────────────────────────────────────


async def test_commission_rule_and_accrual(client, auth_headers, test_company, db_session):
    order_id = await _create_order(client, auth_headers, test_company, db_session, 500.0)

    # rule: 5% for everyone
    rule = await client.post("/api/v1/sales/commission-rules/", json={
        "name": "სტანდარტული 5%", "rate_percent": 5, "fixed_amount": 0,
    }, headers=auth_headers)
    assert rule.status_code == 201, rule.text
    rule_id = rule.json()["data"]["id"]

    # zero rule rejected
    bad = await client.post("/api/v1/sales/commission-rules/", json={
        "name": "ნული", "rate_percent": 0, "fixed_amount": 0,
    }, headers=auth_headers)
    assert bad.status_code == 400

    # accrue manually via DB (service accrual happens on order confirmation;
    # here we simulate the accrual row to test the listing + mark-paid flow)
    async with TestSessionLocal() as session:
        session.add(CommissionAccrual(
            company_id=test_company.id, rule_id=uuid.UUID(rule_id), order_id=uuid.UUID(order_id),
            base_amount=Decimal("500"), commission_amount=Decimal("25"), status="accrued",
        ))
        await session.commit()

    listed = await client.get("/api/v1/sales/commissions/", headers=auth_headers)
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["commission_amount"] == 25.0
    assert items[0]["status"] == "accrued"

    paid = await client.post(f"/api/v1/sales/commissions/{items[0]['id']}/mark-paid", headers=auth_headers)
    assert paid.status_code == 200
    assert paid.json()["data"]["status"] == "paid"
    assert paid.json()["data"]["paid_at"] is not None


async def test_commission_rule_tenant_guard(client, auth_headers, test_company):
    async with TestSessionLocal() as session:
        from app.models.company import Company
        other = Company(name="Other", identification_code=f"OTH-{uuid.uuid4().hex[:6]}",
                        vat_status=False, currency="GEL")
        session.add(other)
        await session.flush()
        rule = CommissionRule(company_id=other.id, name="Sekret", rate_percent=10, fixed_amount=0)
        session.add(rule)
        await session.commit()
        other_rule = str(rule.id)

    resp = await client.patch(f"/api/v1/sales/commission-rules/{other_rule}", json={"is_active": False}, headers=auth_headers)
    assert resp.status_code == 404

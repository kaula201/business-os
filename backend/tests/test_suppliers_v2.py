"""Supplier 2.0: categorization, risk/blacklist, bank approval, multi-currency, onboarding workflow."""
import uuid

import pytest
from sqlalchemy import select

from app.models.purchase import (
    Supplier, SupplierBankDetail, SupplierCurrencyTerm, SupplierOnboardingStep, SupplierRiskEvent,
)
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_supplier(client, auth_headers, **extra):
    payload = {
        "name": f"მომწოდებელი {uuid.uuid4().hex[:4]}", "code": f"SUP-{uuid.uuid4().hex[:6]}",
        "email": f"sup-{uuid.uuid4().hex[:6]}@test.ge", "phone": "599000000",
    }
    payload.update(extra)
    r = await client.post("/api/v1/suppliers/", json=payload, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


async def test_supplier_categorization(client, auth_headers):
    """კატეგორიზაცია: create with category + update category."""
    sid = await _make_supplier(client, auth_headers, category="საკვები")
    r = await client.get(f"/api/v1/suppliers/{sid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["category"] == "საკვები"

    r2 = await client.patch(f"/api/v1/suppliers/{sid}", json={"category": "ლოჯისტიკა"}, headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["category"] == "ლოჯისტიკა"

    # filter by category
    r3 = await client.get("/api/v1/suppliers/?category=ლოჯისტიკა", headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert any(s["id"] == sid for s in r3.json()["data"]["items"])


async def test_supplier_risk_blacklist(client, auth_headers):
    """Blacklist/risk: set risk level + blacklist, audit event trail."""
    sid = await _make_supplier(client, auth_headers)

    r = await client.post(f"/api/v1/suppliers/{sid}/risk", json={
        "risk_level": "high", "risk_score": 85, "is_blacklisted": True,
        "blacklist_reason": "გადახდის ვადების დარღვევა",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["is_blacklisted"] is True
    assert d["risk_level"] == "high"

    # audit event recorded
    r2 = await client.get(f"/api/v1/suppliers/{sid}/risk-events", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    events = r2.json()["data"]
    assert len(events) == 1
    assert events[0]["event_type"] == "blacklist"

    # unblacklist
    r3 = await client.post(f"/api/v1/suppliers/{sid}/risk", json={
        "is_blacklisted": False, "risk_level": "medium",
    }, headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert r3.json()["data"]["is_blacklisted"] is False

    r4 = await client.get(f"/api/v1/suppliers/{sid}/risk-events", headers=auth_headers)
    assert len(r4.json()["data"]) == 2


async def test_bank_account_approval(client, auth_headers, test_company):
    """Bank-account approval: create → pending → approve."""
    sid = await _make_supplier(client, auth_headers)

    r = await client.post(f"/api/v1/suppliers/{sid}/bank-details", json={
        "bank_name": "TBC", "account_name": "შპს ტესტი", "iban": f"GE{uuid.uuid4().hex[:20].upper()}",
        "currency": "GEL", "is_primary": True,
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    bank_id = r.json()["data"]["id"]

    # pending by default
    async with TestSessionLocal() as session:
        bank = (await session.execute(select(SupplierBankDetail).where(SupplierBankDetail.id == uuid.UUID(bank_id)))).scalar_one()
        assert bank.approval_status == "pending"

    r2 = await client.post(f"/api/v1/suppliers/bank-details/{bank_id}/approve", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["approval_status"] == "approved"

    async with TestSessionLocal() as session:
        bank2 = (await session.execute(select(SupplierBankDetail).where(SupplierBankDetail.id == uuid.UUID(bank_id)))).scalar_one()
        assert bank2.approval_status == "approved"
        assert bank2.approved_at is not None


async def test_multi_currency_terms(client, auth_headers):
    """მრავალვალუტიანი პირობები: GEL + USD, default flag, unique per currency."""
    sid = await _make_supplier(client, auth_headers)

    r = await client.post(f"/api/v1/suppliers/{sid}/currency-terms", json={
        "currency": "GEL", "payment_terms_days": 15, "exchange_rate_policy": "daily", "is_default": True,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["is_default"] is True

    r2 = await client.post(f"/api/v1/suppliers/{sid}/currency-terms", json={
        "currency": "USD", "payment_terms_days": 30, "exchange_rate_policy": "fixed", "fixed_rate": 2.7,
    }, headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["fixed_rate"] == 2.7

    # GEL no longer default
    r3 = await client.get(f"/api/v1/suppliers/{sid}/currency-terms", headers=auth_headers)
    assert r3.status_code == 200, r3.text
    terms = r3.json()["data"]
    assert len(terms) == 2
    gel = next(t for t in terms if t["currency"] == "GEL")
    assert gel["is_default"] is True

    # upsert same currency → still 2
    r4 = await client.post(f"/api/v1/suppliers/{sid}/currency-terms", json={
        "currency": "USD", "payment_terms_days": 45,
    }, headers=auth_headers)
    assert r4.status_code == 200, r4.text
    r5 = await client.get(f"/api/v1/suppliers/{sid}/currency-terms", headers=auth_headers)
    assert len(r5.json()["data"]) == 2


async def test_vendor_onboarding_workflow(client, auth_headers):
    """Vendor onboarding workflow: start → steps → complete all → completed."""
    sid = await _make_supplier(client, auth_headers)

    r = await client.post(f"/api/v1/suppliers/{sid}/onboarding/start", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["steps"] == 5

    r2 = await client.get(f"/api/v1/suppliers/{sid}/onboarding", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    d = r2.json()["data"]
    assert d["onboarding_status"] == "in_progress"
    steps = d["steps"]
    assert len(steps) == 5
    assert all(s["status"] == "pending" for s in steps)

    # complete all steps
    for step in steps:
        rc = await client.post(f"/api/v1/suppliers/{sid}/onboarding/{step['id']}/complete", headers=auth_headers)
        assert rc.status_code == 200, rc.text

    r3 = await client.get(f"/api/v1/suppliers/{sid}/onboarding", headers=auth_headers)
    assert r3.json()["data"]["onboarding_status"] == "completed"

    # supplier record reflects completed
    r4 = await client.get(f"/api/v1/suppliers/{sid}", headers=auth_headers)
    assert r4.json()["data"]["onboarding_status"] == "completed"


async def test_supplier_product_terms_link(client, auth_headers):
    """Supplier-product პირობები (procurement-დან): ფასი, ვადა, მინ. რაოდენობა, lead time, პრიორიტეტი."""
    sid = await _make_supplier(client, auth_headers)
    r = await client.post("/api/v1/products/", json={
        "sku": f"PR-{uuid.uuid4().hex[:6]}", "name": "მომწოდებლის პროდუქტი",
        "sale_price": 100, "purchase_price": 50, "unit": "ცალი",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    pid = r.json()["data"]["id"]

    r2 = await client.post("/api/v1/procurement/supplier-products", json={
        "supplier_id": sid, "product_id": pid, "price": 45, "currency": "GEL",
        "min_quantity": 5, "lead_time_days": 7, "priority": 1,
    }, headers=auth_headers)
    assert r2.status_code == 201, r2.text

    r3 = await client.get(f"/api/v1/procurement/supplier-products?supplier_id={sid}", headers=auth_headers)
    assert r3.status_code == 200, r3.text
    items = r3.json()["data"]
    assert len(items) == 1
    assert items[0]["price"] == 45.0
    assert items[0]["min_quantity"] == 5.0
    assert items[0]["lead_time_days"] == 7
    assert items[0]["priority"] == 1

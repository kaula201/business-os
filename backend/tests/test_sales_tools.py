"""Tests for sales tools: quotations, price lists, payment terms."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.client import Client
from app.models.product import Product
from app.models.quotation import Quotation
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed(client, auth_headers, test_company) -> dict:
    async with TestSessionLocal() as session:
        cust = Client(company_id=test_company.id, name="QT Client", client_type="legal",
                      identification_code=f"QT-{uuid.uuid4().hex[:6]}", vat_status=True, status="active")
        prod = Product(company_id=test_company.id, sku=f"QT-SKU-{uuid.uuid4().hex[:6]}",
                       name="QT Product", sale_price=100, current_stock=10)
        session.add_all([cust, prod])
        await session.commit()
        return {"client_id": str(cust.id), "product_id": str(prod.id)}


# ── Payment terms ─────────────────────────────────────────────────────────────


async def test_payment_term_crud(client, auth_headers, test_company):
    created = await client.post("/api/v1/payment-terms/", json={
        "name": "30 დღე", "days": 30, "description": "net 30",
    }, headers=auth_headers)
    assert created.status_code == 201, created.text
    term_id = created.json()["data"]["id"]

    listed = await client.get("/api/v1/payment-terms/", headers=auth_headers)
    assert listed.status_code == 200
    assert any(t["id"] == term_id for t in listed.json()["data"]["items"])

    updated = await client.patch(f"/api/v1/payment-terms/{term_id}", json={"days": 45}, headers=auth_headers)
    assert updated.status_code == 200
    assert updated.json()["data"]["days"] == 45

    deleted = await client.delete(f"/api/v1/payment-terms/{term_id}", headers=auth_headers)
    assert deleted.status_code == 200


# ── Price lists ──────────────────────────────────────────────────────────────


async def test_price_list_crud_with_items(client, auth_headers, test_company):
    seeded = await _seed(client, auth_headers, test_company)
    created = await client.post("/api/v1/price-lists/", json={
        "name": "ოპტიმი", "currency": "GEL", "is_default": True,
        "items": [{"product_id": seeded["product_id"], "price": 80, "min_quantity": 1}],
    }, headers=auth_headers)
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    assert data["is_default"] is True
    assert len(data["items"]) == 1
    assert data["items"][0]["price"] == 80.0

    listed = await client.get("/api/v1/price-lists/", headers=auth_headers)
    assert listed.status_code == 200
    assert any(p["id"] == data["id"] for p in listed.json()["data"]["items"])


async def test_price_list_tenant_guard(client, auth_headers, test_company):
    # product from another company must be rejected
    async with TestSessionLocal() as session:
        from app.models.company import Company
        other = Company(name="Other", identification_code=f"OTH-{uuid.uuid4().hex[:6]}",
                        vat_status=False, currency="GEL")
        session.add(other)
        await session.flush()
        prod = Product(company_id=other.id, sku=f"SKU-{uuid.uuid4().hex[:6]}", name="Other Prod")
        session.add(prod)
        await session.commit()
        other_prod = str(prod.id)

    resp = await client.post("/api/v1/price-lists/", json={
        "name": "გაჟონვა", "items": [{"product_id": other_prod, "price": 1}],
    }, headers=auth_headers)
    assert resp.status_code == 400
    assert "ვერ მოიძებნა" in resp.json()["detail"]


# ── Quotations ───────────────────────────────────────────────────────────────


async def test_quotation_create_and_totals(client, auth_headers, test_company):
    seeded = await _seed(client, auth_headers, test_company)
    resp = await client.post("/api/v1/quotations/", json={
        "client_id": seeded["client_id"], "quotation_date": "2026-08-11",
        "valid_until": "2026-08-25", "items": [
            {"product_id": seeded["product_id"], "description": "QT Product",
             "quantity": 2, "unit_price": 100, "discount_percent": 0},
        ],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["quotation_number"].startswith("QT-20260811-")
    assert data["status"] == "draft"
    assert data["subtotal"] == 200.0
    assert data["vat_amount"] == 36.0   # 200 * 0.18
    assert data["total"] == 236.0
    assert data["client_name"] == "QT Client"


async def test_quotation_workflow_accept_convert(client, auth_headers, test_company):
    seeded = await _seed(client, auth_headers, test_company)
    created = await client.post("/api/v1/quotations/", json={
        "client_id": seeded["client_id"], "quotation_date": "2026-08-11", "items": [
            {"product_id": seeded["product_id"], "description": "P", "quantity": 1, "unit_price": 50},
        ],
    }, headers=auth_headers)
    assert created.status_code == 201
    qid = created.json()["data"]["id"]

    # convert before accept -> 400
    early = await client.post(f"/api/v1/quotations/{qid}/convert", headers=auth_headers)
    assert early.status_code == 400

    accepted = await client.patch(f"/api/v1/quotations/{qid}/status", json={"status": "accepted"}, headers=auth_headers)
    assert accepted.status_code == 200
    assert accepted.json()["data"]["status"] == "accepted"

    converted = await client.post(f"/api/v1/quotations/{qid}/convert", headers=auth_headers)
    assert converted.status_code == 200, converted.text
    order_id = converted.json()["data"]["order_id"]

    # order exists
    orders = await client.get("/api/v1/orders/", headers=auth_headers)
    assert orders.status_code == 200
    assert any(o["id"] == order_id for o in orders.json()["data"]["items"])

    # delete accepted/converted -> 400
    deleted = await client.delete(f"/api/v1/quotations/{qid}", headers=auth_headers)
    assert deleted.status_code == 400

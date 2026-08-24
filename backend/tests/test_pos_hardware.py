"""POS hardware — registers, cashier PIN, TBC/BOG terminals, QR payment, customer deposit."""
import uuid

import pytest
from sqlalchemy import select

from app.models.client import Client
from app.models.pos_extended import POSCashier, POSRegister
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed_client(test_company) -> str:
    async with TestSessionLocal() as session:
        c = Client(company_id=test_company.id, name="POS HW Client", client_type="legal",
                   identification_code=f"HW-{uuid.uuid4().hex[:6]}", vat_status=False, status="active")
        session.add(c)
        await session.commit()
        return str(c.id)


async def test_register_crud(client, auth_headers, test_company):
    r = await client.post("/api/v1/pos/registers", json={"name": "მთავარი სალარო", "code": "REG-01"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    reg_id = r.json()["data"]["id"]
    listed = await client.get("/api/v1/pos/registers", headers=auth_headers)
    assert listed.status_code == 200
    assert any(x["id"] == reg_id for x in listed.json()["data"])


async def test_cashier_pin_verify(client, auth_headers, test_company):
    # pick a user from the company
    from app.models.user import User
    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.company_id == test_company.id).limit(1))).scalar_one()
        uid = str(user.id)

    c = await client.post("/api/v1/pos/cashiers", json={"user_id": uid, "pin": "1234"}, headers=auth_headers)
    assert c.status_code == 201, c.text

    ok = await client.post("/api/v1/pos/cashiers/verify", json={"user_id": uid, "pin": "1234"}, headers=auth_headers)
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["verified"] is True

    bad = await client.post("/api/v1/pos/cashiers/verify", json={"user_id": uid, "pin": "9999"}, headers=auth_headers)
    assert bad.status_code == 401


async def test_payment_terminal_tbc_charge(client, auth_headers, test_company):
    t = await client.post("/api/v1/pos/terminals", json={
        "name": "TBC Term 1", "provider": "tbc", "terminal_id": "TBC-001",
    }, headers=auth_headers)
    assert t.status_code == 201, t.text
    term_id = t.json()["data"]["id"]

    bad_provider = await client.post("/api/v1/pos/terminals", json={
        "name": "Bad", "provider": "visa", "terminal_id": "X",
    }, headers=auth_headers)
    assert bad_provider.status_code == 422

    ch = await client.post(f"/api/v1/pos/terminals/{term_id}/charge", json={"amount": 125.5}, headers=auth_headers)
    assert ch.status_code == 200, ch.text
    data = ch.json()["data"]
    assert data["provider"] == "tbc"
    assert data["status"] == "authorized"
    assert data["amount"] == 125.5


async def test_qr_payment(client, auth_headers, test_company):
    q = await client.post("/api/v1/pos/qr/pay", json={"amount": 45.0}, headers=auth_headers)
    assert q.status_code == 200, q.text
    assert q.json()["data"]["status"] == "paid"
    assert q.json()["data"]["qr_token"]


async def test_customer_deposit(client, auth_headers, test_company):
    cid = await _seed_client(test_company)
    d = await client.post(f"/api/v1/pos/customers/{cid}/deposit", json={"amount": 100}, headers=auth_headers)
    assert d.status_code == 200, d.text
    assert d.json()["data"]["balance"] == 100.0
    bal = await client.get(f"/api/v1/pos/customer-balance/{cid}", headers=auth_headers)
    assert bal.status_code == 200
    assert bal.json()["data"]["balance"] == 100.0

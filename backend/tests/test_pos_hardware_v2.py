"""POS hardware 2.0: TBC/BOG terminal charge (sandbox + live), refund, status, fiscal receipt."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.payment import PaymentTransaction
from app.models.pos_extended import POSPaymentTerminal
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_terminal(client, auth_headers, provider="tbc"):
    r = await client.post("/api/v1/pos/terminals", json={
        "name": "ტერმინალი 1", "provider": provider,
        "terminal_id": f"T-{uuid.uuid4().hex[:6]}", "merchant_id": "M-123",
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def test_terminal_charge_sandbox(client, auth_headers, test_company):
    """Terminal charge: sandbox mode → authorized, transaction recorded, fiscal receipt."""
    tid = await _make_terminal(client, auth_headers, "tbc")

    r = await client.post(f"/api/v1/pos/terminals/{tid}/charge",
                          json={"amount": 150.50, "currency": "GEL", "items": [{"name": "ყავა", "qty": 2, "price": 75.25}]},
                          headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["status"] == "authorized"
    assert d["provider"] == "tbc"
    assert d["gateway"] in ("live", "sandbox")
    assert d["amount"] == 150.5
    assert d["reference"] is not None
    assert d["fiscal_number"] is not None  # fiscal receipt issued (sandbox)

    # transaction recorded
    async with TestSessionLocal() as session:
        tx = (await session.execute(select(PaymentTransaction).where(
            PaymentTransaction.company_id == test_company.id,
        ))).scalars().all()
        assert len(tx) == 1
        assert tx[0].status == "succeeded"
        assert tx[0].provider == "tbc"
        assert tx[0].provider_ref == d["reference"]


async def test_terminal_charge_invalid_amount(client, auth_headers):
    """Terminal charge: zero/negative amount → 422."""
    tid = await _make_terminal(client, auth_headers, "bog")
    r = await client.post(f"/api/v1/pos/terminals/{tid}/charge",
                          json={"amount": 0}, headers=auth_headers)
    assert r.status_code == 422


async def test_terminal_refund(client, auth_headers, test_company):
    """Terminal refund: provider_ref → refunded transaction recorded."""
    tid = await _make_terminal(client, auth_headers, "bog")
    # charge first
    r = await client.post(f"/api/v1/pos/terminals/{tid}/charge",
                          json={"amount": 100}, headers=auth_headers)
    ref = r.json()["data"]["reference"]

    r2 = await client.post(f"/api/v1/pos/terminals/{tid}/refund",
                           json={"provider_ref": ref, "amount": 100}, headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["status"] == "refunded"

    # refund transaction recorded
    async with TestSessionLocal() as session:
        txs = (await session.execute(select(PaymentTransaction).where(
            PaymentTransaction.company_id == test_company.id,
        ))).scalars().all()
        assert len(txs) == 2
        assert any(t.status == "refunded" for t in txs)

    # missing provider_ref → 422
    r3 = await client.post(f"/api/v1/pos/terminals/{tid}/refund",
                           json={"amount": 100}, headers=auth_headers)
    assert r3.status_code == 422


async def test_terminal_status_check(client, auth_headers):
    """Terminal status check: provider_ref → authorized (sandbox)."""
    tid = await _make_terminal(client, auth_headers, "tbc")
    r = await client.post(f"/api/v1/pos/terminals/{tid}/charge",
                          json={"amount": 50}, headers=auth_headers)
    ref = r.json()["data"]["reference"]

    r2 = await client.get(f"/api/v1/pos/terminals/{tid}/status/{ref}", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["status"] in ("authorized", "succeeded", "paid")


async def test_unknown_provider_rejected(client, auth_headers):
    """Terminal create: provider must be tbc or bog."""
    r = await client.post("/api/v1/pos/terminals", json={
        "name": "ცუდი", "provider": "paypal", "terminal_id": "X",
    }, headers=auth_headers)
    assert r.status_code == 422

"""POS extended: gift cards, cash register (X/Z), cash in/out."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.pos_extended import GiftCard, GiftCardTransaction, POSCashMovement, POSZReport
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _open_session(client, auth_headers) -> str:
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Test Shift"}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def test_gift_card_lifecycle(client, auth_headers, test_company, db_session):
    # issue
    resp = await client.post("/api/v1/pos/gift-cards", params={"amount": 100}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    card = resp.json()["data"]
    assert card["balance"] == 100.0
    assert card["card_number"].startswith("GC-")

    # top-up
    resp = await client.post(f"/api/v1/pos/gift-cards/{card['id']}/top-up", params={"amount": 50}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["balance"] == 150.0

    # redeem
    resp = await client.post(f"/api/v1/pos/gift-cards/{card['id']}/redeem", params={"amount": 30}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["balance"] == 120.0

    # over-redeem → 409
    resp = await client.post(f"/api/v1/pos/gift-cards/{card['id']}/redeem", params={"amount": 500}, headers=auth_headers)
    assert resp.status_code == 409, resp.text

    # transactions recorded
    async with TestSessionLocal() as s:
        txs = (await s.execute(select(GiftCardTransaction).where(GiftCardTransaction.card_id == card["id"]))).scalars().all()
        types = {t.transaction_type for t in txs}
        assert types == {"issue", "top_up", "redeem"}


async def test_cash_register_x_z_report(client, auth_headers, test_company, db_session):
    session_id = await _open_session(client, auth_headers)

    # cash in / out
    resp = await client.post(f"/api/v1/pos/sessions/{session_id}/cash-in", params={"amount": 200, "reason": "opening float"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.post(f"/api/v1/pos/sessions/{session_id}/cash-out", params={"amount": 50, "reason": "payout"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text

    # X-report (no close)
    resp = await client.get(f"/api/v1/pos/sessions/{session_id}/x-report", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    x = resp.json()["data"]
    assert x["cash_in"] == 200.0
    assert x["cash_out"] == 50.0
    assert x["expected_cash"] == 150.0

    # Z-report closes the session
    resp = await client.post(f"/api/v1/pos/sessions/{session_id}/z-report", params={"declared_cash": 150}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    z = resp.json()["data"]
    assert z["report_number"].startswith("Z-")
    assert z["difference"] == 0.0

    # session now closed
    resp = await client.get("/api/v1/pos/sessions", headers=auth_headers)
    sessions = resp.json()["data"]
    closed = [s for s in sessions if s["id"] == session_id][0]
    assert closed["status"] == "closed"

    # Z-report persisted
    async with TestSessionLocal() as s:
        report = (await s.execute(select(POSZReport).where(POSZReport.session_id == session_id))).scalar_one()
        assert report.expected_cash == Decimal("150.00")
        assert report.difference == Decimal("0.00")

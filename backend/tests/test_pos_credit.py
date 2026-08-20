"""POS on-account (credit) payment — GL Dr 1300, client balance increases."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.client import Client
from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_client(client, auth_headers) -> str:
    resp = await client.post("/api/v1/clients/", json={
        "name": "Credit Client", "client_type": "individual",
        "identification_code": "CR-001", "credit_limit": 500,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def test_credit_sale_posts_gl_and_balance(client, auth_headers, test_company, db_session):
    from app.services.gl_posting import seed_default_accounts
    await seed_default_accounts(db_session, test_company.id)
    await db_session.commit()

    client_id = await _make_client(client, auth_headers)
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Credit Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "Credit Product", "sku": "CRD-1", "sale_price": 100,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]

    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "client_id": client_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100}],
        "payment_method": "credit",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    assert abs(order["total"] - 118.0) < 0.01

    # GL: Dr 1300 118 / Cr 4100 100 / Cr 2200 18
    async with TestSessionLocal() as s:
        entry = (await s.execute(select(JournalEntry).where(
            JournalEntry.reference_type == "pos_credit", JournalEntry.reference_id == order["id"],
        ))).scalar_one()
        lines = (await s.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))).scalars().all()
        codes = {}
        for l in lines:
            acct = (await s.execute(select(GLAccount).where(GLAccount.id == l.gl_account_id))).scalar_one()
            codes[acct.code] = (float(l.debit_amount), float(l.credit_amount))
        assert codes["1300"] == (118.0, 0.0)
        assert codes["4100"] == (0.0, 100.0)
        assert codes["2200"] == (0.0, 18.0)

        # client balance increased
        c = (await s.execute(select(Client).where(Client.id == client_id))).scalar_one()
        assert c.balance == 118.0


async def test_credit_limit_enforced(client, auth_headers, test_company, db_session):
    from app.services.gl_posting import seed_default_accounts
    await seed_default_accounts(db_session, test_company.id)
    await db_session.commit()

    client_id = await _make_client(client, auth_headers)
    # set the limit directly (clients API may not accept credit_limit)
    async with TestSessionLocal() as s:
        c = (await s.execute(select(Client).where(Client.id == client_id))).scalar_one()
        c.credit_limit = 500
        await s.commit()

    resp = await client.post("/api/v1/pos/sessions", json={"name": "Credit Limit Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "Credit Limit Product", "sku": "CRD-2", "sale_price": 600,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]

    # 600 + 18% = 708 > limit 500 → 409
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "client_id": client_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 600}],
        "payment_method": "credit",
    }, headers=auth_headers)
    assert resp.status_code == 409, resp.text

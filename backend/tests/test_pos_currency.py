"""Multi-currency POS — foreign currency order, GL posts in GEL."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.pos import POSOrder
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_foreign_currency_order(client, auth_headers, test_company, db_session):
    from app.services.gl_posting import seed_default_accounts
    await seed_default_accounts(db_session, test_company.id)
    await db_session.commit()

    resp = await client.post("/api/v1/pos/sessions", json={"name": "FX Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "FX Product", "sku": "FX-1", "sale_price": 100,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]

    # 100 USD + 18% VAT = 118 USD, rate 2.8 → GL total 330.40 GEL
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100}],
        "payment_method": "cash",
        "currency": "USD",
        "currency_rate": 2.8,
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    assert order["currency"] == "USD"
    assert abs(order["total"] - 118.0) < 0.01  # stored in USD
    assert abs(order["currency_rate"] - 2.8) < 0.01

    # GL posts in GEL: Dr 1410 330.40 / Cr 4100 280 / Cr 2200 50.40
    async with TestSessionLocal() as s:
        entry = (await s.execute(select(JournalEntry).where(
            JournalEntry.reference_type == "pos_sale", JournalEntry.reference_id == order["id"],
        ))).scalar_one()
        lines = (await s.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))).scalars().all()
        codes = {}
        for l in lines:
            acct = (await s.execute(select(GLAccount).where(GLAccount.id == l.gl_account_id))).scalar_one()
            codes[acct.code] = (float(l.debit_amount), float(l.credit_amount))
        assert codes["1410"] == (330.40, 0.0)
        assert codes["4100"] == (0.0, 280.0)
        assert codes["2200"] == (0.0, 50.40)

        o = (await s.execute(select(POSOrder).where(POSOrder.id == order["id"]))).scalar_one()
        assert o.currency == "USD"
        assert o.currency_rate == Decimal("2.800000")

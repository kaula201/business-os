"""POS GL integration — every sale/refund posts to the ledger."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_product(client, auth_headers) -> str:
    resp = await client.post("/api/v1/products/", json={
        "name": "GL Product", "sku": "GL-1", "sale_price": 100,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def _line_codes(db, entry_id) -> dict[str, tuple[float, float]]:
    lines = (await db.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry_id))).scalars().all()
    codes = {}
    for l in lines:
        acct = (await db.execute(select(GLAccount).where(GLAccount.id == l.gl_account_id))).scalar_one()
        codes[acct.code] = (float(l.debit_amount), float(l.credit_amount))
    return codes


async def test_pos_sale_posts_gl(client, auth_headers, test_company, db_session):
    from app.services.gl_posting import seed_default_accounts
    await seed_default_accounts(db_session, test_company.id)
    await db_session.commit()

    resp = await client.post("/api/v1/pos/sessions", json={"name": "GL Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    product_id = await _make_product(client, auth_headers)

    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 2, "unit_price": 100}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    assert abs(order["total"] - 236.0) < 0.01  # 200 + 18% VAT

    # GL entry: Dr 1410 236 / Cr 4100 200 / Cr 2200 36
    async with TestSessionLocal() as s:
        entry = (await s.execute(select(JournalEntry).where(
            JournalEntry.reference_type == "pos_sale", JournalEntry.reference_id == order["id"],
        ))).scalar_one()
        codes = await _line_codes(s, entry.id)
        assert codes["1410"] == (236.0, 0.0)
        assert codes["4100"] == (0.0, 200.0)
        assert codes["2200"] == (0.0, 36.0)


async def test_pos_refund_posts_gl(client, auth_headers, test_company, db_session):
    from app.services.gl_posting import seed_default_accounts
    await seed_default_accounts(db_session, test_company.id)
    await db_session.commit()

    resp = await client.post("/api/v1/pos/sessions", json={"name": "GL Refund Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    product_id = await _make_product(client, auth_headers)

    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100}],
        "payment_method": "cash",
    }, headers=auth_headers)
    order = resp.json()["data"]

    resp = await client.post(f"/api/v1/pos/orders/{order['id']}/refund", params={"amount": 118}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    refund_id = resp.json()["data"]["id"]

    # GL entry: Dr 4100 100 / Dr 2200 18 / Cr 1410 118
    async with TestSessionLocal() as s:
        entry = (await s.execute(select(JournalEntry).where(
            JournalEntry.reference_type == "pos_refund", JournalEntry.reference_id == refund_id,
        ))).scalar_one()
        codes = await _line_codes(s, entry.id)
        assert codes["4100"] == (100.0, 0.0)
        assert codes["2200"] == (18.0, 0.0)
        assert codes["1410"] == (0.0, 118.0)


async def test_pos_sale_deducts_stock(client, auth_headers, test_company, db_session):
    """POS sale reduces inventory balance and records a movement."""
    from app.models.warehouse import InventoryBalance, InventoryMovement, Warehouse

    # ensure a default warehouse exists (product creation requires it)
    async with TestSessionLocal() as s:
        wh = (await s.execute(select(Warehouse).where(Warehouse.company_id == test_company.id, Warehouse.is_default.is_(True)))).scalars().first()
        if not wh:
            wh = Warehouse(company_id=test_company.id, code="MAIN", name="მთავარი საწყობი", is_default=True, is_active=True)
            s.add(wh)
            await s.commit()

    # product with stock (products.py auto-creates the balance row)
    resp = await client.post("/api/v1/products/", json={
        "name": "Stock Product", "sku": "STK-1", "sale_price": 50, "current_stock": 10,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    product_id = resp.json()["data"]["id"]

    resp = await client.post("/api/v1/pos/sessions", json={"name": "Stock Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]

    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 3, "unit_price": 50}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text

    # balance reduced 10 → 7, movement recorded
    async with TestSessionLocal() as s:
        bal = (await s.execute(select(InventoryBalance).where(
            InventoryBalance.product_id == product_id, InventoryBalance.company_id == test_company.id,
        ))).scalars().first()
        assert bal is not None
        assert bal.quantity == 7
        mv = (await s.execute(select(InventoryMovement).where(
            InventoryMovement.product_id == product_id, InventoryMovement.reason_category == "sale",
        ))).scalars().first()
        assert mv is not None
        assert mv.quantity == 3
        assert mv.balance_before == 10
        assert mv.balance_after == 7

    # insufficient stock → 409
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 100, "unit_price": 50}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert resp.status_code == 409, resp.text

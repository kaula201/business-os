"""POS fiscal journal — hash-chained immutable sale records."""
import hashlib

import pytest
from sqlalchemy import select

from app.models.pos import POSFiscalJournal
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_fiscal_journal_chain(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/sessions", json={"name": "FJ Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "FJ Product", "sku": "FJ-1", "sale_price": 100,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]

    # two orders → two journal records, chained
    for _ in range(2):
        resp = await client.post("/api/v1/pos/orders", json={
            "session_id": session_id,
            "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100}],
            "payment_method": "cash",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text

    async with TestSessionLocal() as s:
        rows = (await s.execute(select(POSFiscalJournal).where(POSFiscalJournal.company_id == test_company.id).order_by(POSFiscalJournal.created_at.asc()))).scalars().all()
        assert len(rows) == 2
        assert rows[0].prev_hash == "0" * 64  # genesis block
        assert rows[1].prev_hash == rows[0].block_hash  # chained
        # hash integrity
        expected = hashlib.sha256(f"{rows[0].prev_hash}{rows[0].payload_hash}".encode()).hexdigest()
        assert rows[0].block_hash == expected
        expected2 = hashlib.sha256(f"{rows[1].prev_hash}{rows[1].payload_hash}".encode()).hexdigest()
        assert rows[1].block_hash == expected2

    # endpoint reports chain valid
    resp = await client.get("/api/v1/pos/fiscal-journal", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["count"] == 2
    assert data["chain_valid"] is True

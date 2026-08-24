"""P1-3: POS session/cash reconciliation — opening cash + sales + Z-report."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.pos import POSSession
from app.models.pos_extended import POSZReport
from app.models.product import Product
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed_product(client, auth_headers, test_company):
    async with TestSessionLocal() as session:
        prod = Product(company_id=test_company.id, sku=f"POSR-{uuid.uuid4().hex[:6]}",
                       name="POS Recon", sale_price=100, purchase_price=60, current_stock=10)
        session.add(prod)
        await session.commit()
        return str(prod.id)


async def test_pos_z_report_reconciliation(client, auth_headers, test_company):
    product_id = await _seed_product(client, auth_headers, test_company)

    # 1. Open session with 500 opening cash
    sess = await client.post("/api/v1/pos/sessions", json={"name": "Shift 1", "opening_cash": 500}, headers=auth_headers)
    assert sess.status_code == 201, sess.text
    session_id = sess.json()["data"]["id"]
    assert sess.json()["data"]["opening_cash"] == 500.0

    # 2. Cash sale 118 (100 + 18 VAT)
    order = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert order.status_code == 201, order.text

    # 3. Z-report: expected cash = 500 opening + 118 sales = 618
    z = await client.post(f"/api/v1/pos/sessions/{session_id}/z-report", json={"declared_cash": 618}, headers=auth_headers)
    assert z.status_code == 200, z.text
    data = z.json()["data"]
    assert data["expected_cash"] == 618.0, f"expected={data['expected_cash']}"
    assert data["difference"] == 0.0, f"diff={data['difference']}"

    # 4. Session closed + Z report persisted
    async with TestSessionLocal() as s:
        session = (await s.execute(select(POSSession).where(POSSession.id == session_id))).scalar_one()
        assert session.status == "closed"
        report = (await s.execute(select(POSZReport).where(POSZReport.session_id == session_id))).scalar_one()
        assert report.expected_cash == Decimal("618.00")
        assert report.difference == Decimal("0.00")

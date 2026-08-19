"""Auto-detect intercompany eliminations from invoices to group companies."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.company import Company
from app.models.consolidation_elimination import ConsolidationElimination
from app.models.invoice import Invoice
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_group_company(db, suffix: str, group_id, identification_code: str) -> Company:
    comp = Company(
        name=f"Group Co {suffix}",
        identification_code=identification_code,
        company_group_id=group_id,
        vat_status=True,
        currency="GEL",
    )
    db.add(comp)
    await db.flush()
    return comp


async def _invoice_to_company(db, issuer_company: Company, buyer_company: Company, number: str, subtotal: Decimal, date_iso: str) -> Invoice:
    from app.models.client import Client
    client = Client(
        company_id=issuer_company.id,
        name=buyer_company.name,
        client_type="legal",
        identification_code=buyer_company.identification_code,
        vat_status=True,
        status="active",
    )
    db.add(client)
    await db.flush()
    from app.models.order import Order
    order = Order(
        company_id=issuer_company.id,
        client_id=client.id,
        order_number=f"ORD-IC-{number}",
        status="confirmed",
        subtotal=float(subtotal),
        vat_amount=0,
        total=float(subtotal),
    )
    db.add(order)
    await db.flush()
    inv = Invoice(
        company_id=issuer_company.id,
        client_id=client.id,
        order_id=order.id,
        invoice_number=number,
        idempotency_key=f"ic-{number}",
        status="issued",
        invoice_date=date.fromisoformat(date_iso),
        due_date=date.fromisoformat("2026-09-01"),
        currency="GEL",
        subtotal=subtotal,
        vat_amount=Decimal("0"),
        total=subtotal,
        order_number="ORD-IC",
        seller_name=issuer_company.name,
        seller_identification_code=issuer_company.identification_code,
        client_name=buyer_company.name,
        client_identification_code=buyer_company.identification_code,
    )
    db.add(inv)
    await db.flush()
    return inv


async def test_auto_detect_creates_draft_eliminations(db_session, auth_headers, test_company, client):
    # group id for test company + a second group company
    group_id = uuid.uuid4()
    async with TestSessionLocal() as s:
        c = (await s.execute(select(Company).where(Company.id == test_company.id))).scalar_one()
        c.company_group_id = group_id
        await s.commit()

    other = await _make_group_company(db_session, "B", group_id, "GRP-B-001")
    await db_session.commit()

    # invoice issued to the group company
    inv = await _invoice_to_company(db_session, test_company, other, "IC-001", Decimal("500.00"), "2026-08-15")
    await db_session.commit()

    resp = await client.post("/api/v1/gl/consolidation-eliminations/auto-detect", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["created"] == 1
    assert data["items"][0]["invoice_number"] == "IC-001"

    row = (await db_session.execute(select(ConsolidationElimination).where(
        ConsolidationElimination.idempotency_key == f"auto:{inv.id}",
    ))).scalar_one()
    assert row.status == "draft"
    assert row.amount == Decimal("500.00")
    assert row.source_revenue_account_code == "4100"
    assert row.counterparty_company_id == other.id

    # second run → skipped (idempotent)
    resp2 = await client.post("/api/v1/gl/consolidation-eliminations/auto-detect", headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["created"] == 0
    assert resp2.json()["data"]["skipped"] == 1


async def test_auto_detect_skips_non_group_client(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/gl/consolidation-eliminations/auto-detect", headers=auth_headers)
    assert resp.status_code == 422, resp.text  # no group

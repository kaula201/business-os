"""Intercompany purchase-side auto-match from supplier invoices to group companies."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.company import Company
from app.models.consolidation_elimination import ConsolidationElimination
from app.models.purchase import Supplier, SupplierInvoice
from app.models.warehouse import Warehouse
from app.models.product import Product
from app.models.purchase import PurchaseOrder
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed_purchase_invoice(db, company, group_company_id: uuid.UUID, suffix: str, subtotal: Decimal, date_iso: str) -> str:
    supplier = Supplier(
        company_id=company.id, code=f"IC-SUP-{suffix}", name=f"IC Supplier {suffix}",
        identification_code=f"IC-CODE-{suffix}", is_vat_payer=False,
    )
    db.add(supplier)
    await db.flush()
    wh = Warehouse(company_id=company.id, code=f"IC-WH-{suffix}", name="IC WH", is_default=True, is_active=True)
    db.add(wh)
    await db.flush()
    product = Product(company_id=company.id, sku=f"IC-P-{suffix}", name="IC Product", sale_price=10, current_stock=0)
    db.add(product)
    await db.flush()
    po = PurchaseOrder(
        company_id=company.id, supplier_id=supplier.id, warehouse_id=wh.id,
        purchase_order_number=f"PO-IC-{suffix}", status="approved",
        subtotal=subtotal, vat_amount=Decimal("0"), total=subtotal,
    )
    db.add(po)
    await db.flush()
    inv = SupplierInvoice(
        company_id=company.id, supplier_id=supplier.id, purchase_order_id=po.id,
        internal_invoice_number=f"SI-IC-{suffix}", supplier_invoice_number=f"SUP-IC-{suffix}",
        invoice_date=date.fromisoformat(date_iso), due_date=date.fromisoformat("2026-09-01"),
        status="approved", matching_status="matched",
        subtotal=subtotal, vat_amount=Decimal("0"), total=subtotal,
    )
    db.add(inv)
    await db.flush()
    return str(inv.id)


async def test_auto_detect_purchases(client, auth_headers, test_company, db_session):
    # group test company with a second company
    group_id = uuid.uuid4()
    async with TestSessionLocal() as s:
        c = (await s.execute(select(Company).where(Company.id == test_company.id))).scalar_one()
        c.company_group_id = group_id
        await s.commit()
    other = Company(
        name="IC Group Co", identification_code="IC-CODE-A",
        company_group_id=group_id, is_active=True, vat_status=True, currency="GEL",
    )
    db_session.add(other)
    await db_session.commit()

    inv_id = await _seed_purchase_invoice(db_session, test_company, other.id, "A", Decimal("800"), "2026-08-10")
    await db_session.commit()

    resp = await client.post("/api/v1/gl/consolidation-eliminations/auto-detect-purchases", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["created"] == 1
    assert data["items"][0]["invoice_number"] == "SUP-IC-A"

    row = (await db_session.execute(select(ConsolidationElimination).where(
        ConsolidationElimination.idempotency_key == f"auto-purchase:{inv_id}",
    ))).scalar_one()
    assert row.amount == Decimal("800.00")
    assert row.counterparty_company_id == other.id

    # idempotent
    resp2 = await client.post("/api/v1/gl/consolidation-eliminations/auto-detect-purchases", headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["created"] == 0
    assert resp2.json()["data"]["skipped"] == 1

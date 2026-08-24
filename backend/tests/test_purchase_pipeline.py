"""P1-2: RFQ → PO → Receipt → Supplier Invoice → Payment → GL — full purchase pipeline E2E."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.client import Client
from app.models.gl import GLAccount, JournalEntryLine
from app.models.product import Product
from app.models.purchase import Supplier
from app.models.warehouse import Warehouse
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed(client, auth_headers, test_company):
    async with TestSessionLocal() as session:
        sup = Supplier(company_id=test_company.id, name="Pipe Supplier", code=f"SUP-{uuid.uuid4().hex[:6]}",
                       identification_code=f"SUP-{uuid.uuid4().hex[:6]}", is_active=True, is_vat_payer=True)
        wh = Warehouse(company_id=test_company.id, name="Main WH", code="WH1", is_active=True)
        prod = Product(company_id=test_company.id, sku=f"BUY-SKU-{uuid.uuid4().hex[:6]}",
                       name="Buy Product", sale_price=150, purchase_price=60, current_stock=0)
        session.add_all([sup, wh, prod])
        await session.commit()
        return {"supplier_id": str(sup.id), "warehouse_id": str(wh.id), "product_id": str(prod.id)}


async def test_full_purchase_pipeline_to_gl(client, auth_headers, test_company):
    seeded = await _seed(client, auth_headers, test_company)

    # 1. PO (RFQ → PO)
    po = await client.post("/api/v1/purchase-orders/", json={
        "supplier_id": seeded["supplier_id"], "warehouse_id": seeded["warehouse_id"],
        "order_date": "2026-08-11", "expected_date": "2026-08-20",
        "items": [{"product_id": seeded["product_id"], "quantity": 10, "unit_price": 60, "vat_rate": 18}],
    }, headers=auth_headers)
    assert po.status_code in (200, 201), po.text
    po_id = po.json()["data"]["id"]
    po_item_id = po.json()["data"]["items"][0]["id"]

    # 2. Approve
    appr = await client.patch(f"/api/v1/purchase-orders/{po_id}/status", json={"status": "approved"}, headers=auth_headers)
    assert appr.status_code == 200, appr.text

    # 3. Receipt
    rec = await client.post(f"/api/v1/purchase-orders/{po_id}/receipts", json={
        "idempotency_key": f"recv-{uuid.uuid4().hex[:8]}",
        "items": [{"purchase_order_item_id": po_item_id, "quantity": 10}],
    }, headers=auth_headers)
    assert rec.status_code in (200, 201), rec.text

    # 4. Supplier invoice
    inv = await client.post("/api/v1/supplier-invoices/", json={
        "supplier_id": seeded["supplier_id"], "purchase_order_id": po_id,
        "supplier_invoice_number": f"SI-{uuid.uuid4().hex[:6]}",
        "invoice_date": "2026-08-12", "due_date": "2026-09-12",
        "items": [{"purchase_order_item_id": po_item_id, "quantity": 10, "unit_price": 60, "vat_rate": 18}],
    }, headers=auth_headers)
    assert inv.status_code in (200, 201), inv.text
    invoice_id = inv.json()["data"]["id"]

    # 4b. Approve invoice → payable created + GL posted
    appr_inv = await client.patch(f"/api/v1/supplier-invoices/{invoice_id}/status", json={"status": "approved"}, headers=auth_headers)
    assert appr_inv.status_code == 200, appr_inv.text

    # 5. Payable exists → pay
    payables = await client.get("/api/v1/supplier-payables/", params={"invoice_id": invoice_id}, headers=auth_headers)
    assert payables.status_code == 200, payables.text
    payable_items = payables.json()["data"]["items"]
    assert len(payable_items) >= 1, "payable not created from supplier invoice"
    payable_id = payable_items[0]["id"]
    pay = await client.post(f"/api/v1/supplier-payables/{payable_id}/payments", json={
        "idempotency_key": f"pay-{uuid.uuid4().hex[:8]}", "amount": 708,
        "payment_date": "2026-08-13", "payment_method": "bank_transfer",
    }, headers=auth_headers)
    assert pay.status_code in (200, 201), pay.text

    # 6. GL verification: 1200 inventory +600, 2100 AP cleared, 1410 -708, 2200 input VAT +108
    async with TestSessionLocal() as s:
        accounts = (await s.execute(select(GLAccount).where(GLAccount.company_id == test_company.id))).scalars().all()
        acc = {a.code: a for a in accounts}
        balances = {}
        for code, a in acc.items():
            row = (await s.execute(
                select(
                    func.coalesce(func.sum(JournalEntryLine.debit_amount), 0),
                    func.coalesce(func.sum(JournalEntryLine.credit_amount), 0),
                ).where(JournalEntryLine.gl_account_id == a.id)
            )).one()
            dr, cr = Decimal(row[0]), Decimal(row[1])
            balances[code] = dr - cr if a.account_type in ("asset", "expense") else cr - dr

        assert balances.get("1200", Decimal("0")) == Decimal("600.00"), f"1200={balances.get('1200')}"
        assert balances.get("2100", Decimal("0")) == Decimal("0.00"), f"2100={balances.get('2100')} (should be cleared)"
        assert balances.get("1410", Decimal("0")) == Decimal("-708.00"), f"1410={balances.get('1410')}"
        assert balances.get("5300", Decimal("0")) == Decimal("108.00"), f"5300={balances.get('5300')} (VAT input)"

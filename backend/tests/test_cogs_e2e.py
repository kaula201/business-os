"""COGS/stock-cost E2E: purchase cost flows into P&L through the ledger.

Business OS uses purchase-based COGS: supplier invoices post the cost to
5100 (COGS) at purchase time, sales post revenue to 4100 at invoice time,
and the P&L report aggregates both from GL balances. This test proves the
whole chain stays consistent: stock cost, GL entries, and P&L amounts.
"""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.gl import JournalEntryLine
from app.models.product import Product
from app.models.warehouse import InventoryBalance, Warehouse


async def create_cogs_context(client, auth_headers, test_company, db_session, suffix: str):
    product = Product(
        company_id=test_company.id,
        sku=f"COGS-{suffix}",
        name=f"COGS Product {suffix}",
        sale_price=100,
        purchase_price=10,
        unit="ცალი",
        min_stock=0,
        current_stock=0,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code=f"COGS-WH-{suffix}",
        name=f"COGS Warehouse {suffix}",
        is_default=True,
        is_active=True,
    )
    db_session.add_all([product, warehouse])
    await db_session.flush()
    db_session.add(
        InventoryBalance(
            company_id=test_company.id,
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=Decimal("0"),
        )
    )
    await db_session.commit()
    await db_session.refresh(product)

    supplier_res = await client.post(
        "/api/v1/suppliers/",
        json={
            "code": f"COGS-SUP-{suffix}",
            "name": f"COGS Supplier {suffix}",
            "identification_code": f"{uuid4().int % 900000000 + 100000000}",
            "is_vat_payer": True,
            "contact_name": "COGS Contact",
            "phone": "+995500000004",
            "email": f"cogs{suffix}@supplier.ge",
            "payment_terms_days": 30,
        },
        headers=auth_headers,
    )
    assert supplier_res.status_code == 200, supplier_res.text

    client_res = await client.post(
        "/api/v1/clients/",
        json={
            "name": f"COGS Client {suffix}",
            "client_type": "legal",
            "identification_code": f"{uuid4().int % 900000000 + 100000000}",
            "status": "active",
            "is_vat_payer": False,
        },
        headers=auth_headers,
    )
    assert client_res.status_code == 200, client_res.text
    return product, warehouse, supplier_res.json()["data"], client_res.json()["data"]


async def run_purchase_flow(client, auth_headers, product, warehouse, supplier, suffix: str):
    """PO -> receipt -> supplier invoice (approved) -> payable."""
    po_res = await client.post(
        "/api/v1/purchase-orders/",
        json={
            "supplier_id": supplier["id"],
            "warehouse_id": str(warehouse.id),
            "expected_delivery_date": (date.today() + timedelta(days=10)).isoformat(),
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 10,
                    "unit_price": 10,
                    "discount_percent": 0,
                    "vat_rate": 18,
                }
            ],
        },
        headers=auth_headers,
    )
    assert po_res.status_code == 200, po_res.text
    po = po_res.json()["data"]
    po_item_id = po["items"][0]["id"]
    approved = await client.patch(
        f"/api/v1/purchase-orders/{po['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text
    receipt = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/receipts",
        json={
            "idempotency_key": f"cogs-{suffix}-receipt",
            "items": [{"purchase_order_item_id": po_item_id, "quantity": 10}],
        },
        headers=auth_headers,
    )
    assert receipt.status_code == 200, receipt.text

    invoice_res = await client.post(
        "/api/v1/supplier-invoices/",
        json={
            "supplier_id": supplier["id"],
            "purchase_order_id": po["id"],
            "supplier_invoice_number": f"COGS-INV-{suffix}",
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=30)).isoformat(),
            "items": [
                {
                    "purchase_order_item_id": po_item_id,
                    "quantity": 10,
                    "unit_price": 10,
                    "discount_percent": 0,
                    "vat_rate": 18,
                }
            ],
        },
        headers=auth_headers,
    )
    assert invoice_res.status_code == 200, invoice_res.text
    invoice = invoice_res.json()["data"]
    approved_inv = await client.patch(
        f"/api/v1/supplier-invoices/{invoice['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved_inv.status_code == 200, approved_inv.text
    return po


async def run_sale_flow(client, auth_headers, product, warehouse, customer, suffix: str):
    """Order (confirmed) -> invoice issued."""
    order_res = await client.post(
        "/api/v1/orders/",
        json={
            "client_id": customer["id"],
            "warehouse_id": str(warehouse.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "quantity": 6,
                    "unit_price": 100,
                    "discount_percent": 0,
                }
            ],
            "is_vat_payer": False,
        },
        headers=auth_headers,
    )
    assert order_res.status_code == 200, order_res.text
    order_id = order_res.json()["data"]["id"]
    confirmed = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "confirmed"},
        headers=auth_headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    # ship → COGS posted (Dr 5100 / Cr 1200)
    shipped = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "shipping"},
        headers=auth_headers,
    )
    assert shipped.status_code == 200, shipped.text
    invoice_res = await client.post(
        "/api/v1/invoices/generate",
        json={
            "order_id": order_id,
            "idempotency_key": f"cogs-{suffix}-sale-invoice",
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
        },
        headers=auth_headers,
    )
    assert invoice_res.status_code == 200, invoice_res.text
    return invoice_res.json()["data"]


async def gl_balance_for(db_session, company_id, account_code: str) -> Decimal:
    """Net GL balance (debit - credit) for an account."""
    rows = (
        await db_session.execute(
            select(
                JournalEntryLine.gl_account_id,
                JournalEntryLine.debit_amount,
                JournalEntryLine.credit_amount,
            )
            .join(
                __import__("app.models.gl", fromlist=["JournalEntry"]).JournalEntry,
                JournalEntryLine.journal_entry_id
                == __import__("app.models.gl", fromlist=["JournalEntry"]).JournalEntry.id,
            )
            .where(
                __import__("app.models.gl", fromlist=["JournalEntry"]).JournalEntry.company_id
                == company_id
            )
        )
    ).all()
    account = (
        await db_session.execute(
            select(__import__("app.models.gl", fromlist=["GLAccount"]).GLAccount).where(
                __import__("app.models.gl", fromlist=["GLAccount"]).GLAccount.code
                == account_code
            )
        )
    ).scalar_one()
    balance = Decimal("0")
    for row in rows:
        if row.gl_account_id == account.id:
            balance += Decimal(row.debit_amount) - Decimal(row.credit_amount)
    return balance


@pytest.mark.asyncio
async def test_cogs_flows_from_purchase_to_profit_loss(
    client, auth_headers, test_company, db_session
):
    product, warehouse, supplier, customer = await create_cogs_context(
        client, auth_headers, test_company, db_session, "FLOW"
    )

    await run_purchase_flow(
        client, auth_headers, product, warehouse, supplier, "FLOW"
    )
    await run_sale_flow(
        client, auth_headers, product, warehouse, customer, "FLOW"
    )

    # GL: COGS (5100) has debit 60 (6 units x 10); Revenue (4100) credit 600
    cogs_balance = await gl_balance_for(db_session, test_company.id, "5100")
    revenue_balance = await gl_balance_for(db_session, test_company.id, "4100")
    assert cogs_balance == Decimal("60")
    assert revenue_balance == Decimal("-600")

    # P&L report aggregates them: COGS (5100) 60 + VAT expense (5300) 18 = 78
    pl_res = await client.get(
        "/api/v1/gl/profit-loss/",
        params={
            "start_date": (date.today() - timedelta(days=1)).isoformat(),
            "end_date": (date.today() + timedelta(days=1)).isoformat(),
        },
        headers=auth_headers,
    )
    assert pl_res.status_code == 200, pl_res.text
    pl = pl_res.json()["data"]

    income_total = sum(
        float(a["balance"]) for a in pl.get("income_accounts", [])
    )
    expense_total = sum(
        float(a["balance"]) for a in pl.get("expense_accounts", [])
    )
    # Expense balances must be POSITIVE (debit side): COGS 60 + VAT 18
    assert abs(income_total - 600) < 0.01
    assert abs(expense_total - 78) < 0.01
    assert abs(float(pl.get("net_income", 0)) - 522) < 0.01


@pytest.mark.asyncio
async def test_partial_sale_reduces_stock_but_cogs_stays_purchase_based(
    client, auth_headers, test_company, db_session
):
    product, warehouse, supplier, customer = await create_cogs_context(
        client, auth_headers, test_company, db_session, "PARTIAL"
    )
    await run_purchase_flow(
        client, auth_headers, product, warehouse, supplier, "PARTIAL"
    )
    await run_sale_flow(
        client, auth_headers, product, warehouse, customer, "PARTIAL"
    )

    # Odoo-style: shipping decrements stock (10 - 6 = 4) and posts COGS
    await db_session.refresh(product)
    balance = (
        await db_session.execute(
            select(InventoryBalance).where(
                InventoryBalance.company_id == test_company.id,
                InventoryBalance.product_id == product.id,
            )
        )
    ).scalar_one()
    assert balance.quantity == Decimal("4")

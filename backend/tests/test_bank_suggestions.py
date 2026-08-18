"""Bank reconciliation suggestions: confidence scoring and candidate matching."""
import uuid
from datetime import date
from decimal import Decimal

import pytest

from tests.test_bank_reconciliation import create_bank_account, import_statement
from tests.test_supplier_credit_reversals import create_approved_payable

pytestmark = pytest.mark.asyncio


async def test_reconciliation_suggestions_returns_high_confidence_match(client, auth_headers, test_company, db_session):
    payable = await create_approved_payable(client, auth_headers, test_company, db_session, "SUGG")
    payable_amount = Decimal(str(payable["outstanding_amount"]))

    account = await create_bank_account(client, auth_headers, "SUGG")
    csv_content = (
        "transaction_date,reference,description,counterparty,amount,direction,currency\n"
        f"{date.today()},BANK-SUGG-1,Supplier payment,Supplier One,{payable_amount},debit,GEL\n"
    )
    imported = await client.post(
        f"/api/v1/bank-accounts/{account['id']}/statement-imports",
        json={"idempotency_key": "statement-sugg", "filename": "sugg.csv", "csv_content": csv_content},
        headers=auth_headers,
    )
    assert imported.status_code == 200, imported.text

    resp = await client.get("/api/v1/reconciliation-suggestions", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["candidates"], "expected at least one candidate"
    assert data[0]["candidates"][0]["confidence"] == 100
    assert data[0]["candidates"][0]["kind"] == "payable"


async def test_suggestions_skip_cross_currency_payable(client, auth_headers, test_company, db_session):
    """A payable in a different currency must never be suggested for a GEL debit."""
    payable = await create_approved_payable(client, auth_headers, test_company, db_session, "SUGGXC")
    from sqlalchemy import select
    from app.models.purchase import SupplierPayable
    from tests.conftest import TestSessionLocal
    async with TestSessionLocal() as s:
        p = (await s.execute(select(SupplierPayable).where(SupplierPayable.id == uuid.UUID(payable["id"])))).scalar_one()
        p.currency_code = "USD"
        await s.commit()

    account = await create_bank_account(client, auth_headers, "SUGGXC")
    csv_content = (
        "transaction_date,reference,description,counterparty,amount,direction,currency\n"
        f"{date.today()},BANK-SUGG-XC,Supplier payment,Supplier One,100.00,debit,GEL\n"
    )
    imported = await client.post(
        f"/api/v1/bank-accounts/{account['id']}/statement-imports",
        json={"idempotency_key": "statement-sugg-xc", "filename": "xc.csv", "csv_content": csv_content},
        headers=auth_headers,
    )
    assert imported.status_code == 200, imported.text

    resp = await client.get("/api/v1/reconciliation-suggestions", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["candidates"] == [], "cross-currency payable must be excluded"

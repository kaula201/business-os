"""Batch bank reconciliation approval: payable and receivable in one call."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.banking import BankReconciliation
from app.models.receivable import CustomerBankReconciliation
from app.models.purchase import SupplierPayable
from tests.conftest import TestSessionLocal
from tests.test_bank_reconciliation import create_bank_account
from tests.test_customer_receivables import create_receivable
from tests.test_supplier_credit_reversals import create_approved_payable

pytestmark = pytest.mark.asyncio


async def test_batch_approve_payable_and_receivable(client, auth_headers, test_company, db_session):
    payable = await create_approved_payable(client, auth_headers, test_company, db_session, "BATCH")
    payable_amount = Decimal(str(payable["outstanding_amount"]))

    receivable = await create_receivable(client, auth_headers, test_company, db_session, "BATCHR")
    receivable = receivable[1]
    receivable_amount = Decimal(str(receivable["outstanding_amount"]))

    account = await create_bank_account(client, auth_headers, "BATCH")
    csv_content = (
        "transaction_date,reference,description,counterparty,amount,direction,currency\n"
        f"{date.today()},BATCH-OUT,Supplier payment,Supplier,{payable_amount},debit,GEL\n"
        f"{date.today()},BATCH-IN,Customer receipt,Client,{receivable_amount},credit,GEL\n"
    )
    imported = await client.post(
        f"/api/v1/bank-accounts/{account['id']}/statement-imports",
        json={"idempotency_key": "statement-batch", "filename": "batch.csv", "csv_content": csv_content},
        headers=auth_headers,
    )
    assert imported.status_code == 200, imported.text

    txns = await client.get("/api/v1/bank-transactions/", headers=auth_headers)
    items = {t["direction"]: t for t in txns.json()["data"]["items"]}
    debit_txn = items["debit"]
    credit_txn = items["credit"]

    resp = await client.post("/api/v1/bank-reconciliations/batch-approve", json={
        "items": [
            {"transaction_id": debit_txn["id"], "kind": "payable", "candidate_id": payable["id"], "amount": float(payable_amount)},
            {"transaction_id": credit_txn["id"], "kind": "receivable", "candidate_id": receivable["id"], "amount": float(receivable_amount)},
        ]
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["processed"] == 2
    assert all(r["reconciliation_id"] for r in data["results"])

    # Idempotent replay returns the same reconciliation ids.
    replay = await client.post("/api/v1/bank-reconciliations/batch-approve", json={
        "items": [
            {"transaction_id": debit_txn["id"], "kind": "payable", "candidate_id": payable["id"], "amount": float(payable_amount)},
            {"transaction_id": credit_txn["id"], "kind": "receivable", "candidate_id": receivable["id"], "amount": float(receivable_amount)},
        ]
    }, headers=auth_headers)
    replay_data = replay.json()["data"]
    assert replay_data["processed"] == 2
    assert [r["reconciliation_id"] for r in replay_data["results"]] == [r["reconciliation_id"] for r in data["results"]]

    # GL + balances updated.
    async with TestSessionLocal() as s:
        p = (await s.execute(select(SupplierPayable).where(SupplierPayable.id == uuid.UUID(payable["id"])))).scalar_one()
        assert p.outstanding_amount == 0
        assert p.status == "paid"

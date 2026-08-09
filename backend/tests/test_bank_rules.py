"""Tests for bank reconciliation rules: categorize + auto-reconcile."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.bank_rule import BankReconciliationRule
from app.models.banking import BankReconciliation, BankTransaction
from app.models.gl import JournalEntry
from app.models.purchase import SupplierPayment
from tests.test_bank_reconciliation import create_bank_account, import_statement
from tests.test_supplier_credit_reversals import create_approved_payable
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _create_rule(client, auth_headers, payload: dict):
    resp = await client.post("/api/v1/banking/reconciliation-rules/", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _get_gl_account_id(client, auth_headers, code: str) -> str:
    resp = await client.get("/api/v1/gl/accounts/", headers=auth_headers, params={"page_size": 200})
    assert resp.status_code == 200
    for a in resp.json()["data"]["items"]:
        if a["code"] == code:
            return a["id"]
    raise AssertionError(f"GL account {code} not seeded")


async def _get_transactions(client, auth_headers, account_id: str):
    resp = await client.get("/api/v1/bank-transactions/", headers=auth_headers, params={"page_size": 100, "bank_account_id": account_id})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["items"]


# ── Categorize rule ──────────────────────────────────────────────────────────


async def test_categorize_rule_marks_transaction(client, auth_headers, test_company):
    account = await create_bank_account(client, auth_headers, "CAT")
    imported, _ = await import_statement(client, auth_headers, account["id"], "CAT")
    gl_id = await _get_gl_account_id(client, auth_headers, "5200")

    await _create_rule(client, auth_headers, {
        "name": "საბანკო საკომისიო", "rule_type": "description_contains",
        "action": "categorize", "match_text": "Supplier payment",
        "gl_account_id": gl_id, "priority": 10,
    })

    resp = await client.post("/api/v1/banking/reconciliation-rules/apply", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["categorized"] == 1
    assert data["matched"] == 0

    txns = await _get_transactions(client, auth_headers, account["id"])
    debit = next(t for t in txns if t["direction"] == "debit")
    assert debit["status"] == "categorized"


# ── Auto-reconcile rule (amount_date) ────────────────────────────────────────


async def test_auto_reconcile_rule_matches_payable(client, auth_headers, test_company, db_session):
    # Create a payable (default 10 x 10.00 = 100.00)
    payable = await create_approved_payable(
        client, auth_headers, test_company, db_session, "ARX"
    )
    payable_amount = Decimal(str(payable["outstanding_amount"]))

    # Import a statement whose debit matches the payable amount exactly
    account = await create_bank_account(client, auth_headers, "ARX")
    csv_content = (
        "transaction_date,reference,description,counterparty,amount,direction,currency\n"
        f"{date.today()},BANK-ARX-1,Supplier payment,Supplier One,{payable_amount},debit,GEL\n"
    )
    imported = await client.post(
        f"/api/v1/bank-accounts/{account['id']}/statement-imports",
        json={
            "idempotency_key": "statement-arx",
            "filename": "statement-arx.csv",
            "csv_content": csv_content,
        },
        headers=auth_headers,
    )
    assert imported.status_code == 200, imported.text

    await _create_rule(client, auth_headers, {
        "name": "ავტო-შეჯერება", "rule_type": "amount_date",
        "action": "auto_reconcile", "match_amount": -float(payable_amount),
        "date_window_days": 7, "direction": "out", "priority": 5,
    })

    resp = await client.post("/api/v1/banking/reconciliation-rules/apply", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["matched"] == 1, resp.text

    # Reconciliation + payment exist
    async with TestSessionLocal() as s:
        recon = (await s.execute(select(BankReconciliation))).scalars().first()
        assert recon is not None
        payment = (await s.execute(select(SupplierPayment))).scalars().first()
        assert payment is not None
        assert recon.amount == payable_amount

        # GL entry posted (supplier_bank_reconciliation)
        entry = (await s.execute(select(JournalEntry).where(
            JournalEntry.reference_type == "supplier_bank_reconciliation",
        ))).scalars().first()
        assert entry is not None


# ── Negative: no match → skipped ─────────────────────────────────────────────


async def test_apply_without_matching_rule_skips(client, auth_headers, test_company):
    account = await create_bank_account(client, auth_headers, "NEG")
    imported, _ = await import_statement(client, auth_headers, account["id"], "NEG")

    # Rule with a text that matches nothing
    await _create_rule(client, auth_headers, {
        "name": "არაფერი", "rule_type": "counterparty_equals",
        "action": "categorize", "match_text": "NOBODY",
        "gl_account_id": await _get_gl_account_id(client, auth_headers, "5200"),
    })

    resp = await client.post("/api/v1/banking/reconciliation-rules/apply", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["categorized"] == 0
    assert data["matched"] == 0

    txns = await _get_transactions(client, auth_headers, account["id"])
    assert all(t["status"] == "unmatched" for t in txns)

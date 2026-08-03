from datetime import date

import pytest
from sqlalchemy import select, text

from app.models.audit import AuditLog
from app.models.user import User
from tests.test_bank_reconciliation import create_bank_account, import_statement
from tests.test_customer_invoicing import create_invoice_order, invoice_payload
from tests.test_supplier_credit_reversals import create_user_headers


async def create_receivable(client, auth_headers, test_company, db_session, suffix: str):
    order, _, _ = await create_invoice_order(
        client, auth_headers, test_company, db_session, f"AR-{suffix}"
    )
    issued = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], f"AR-{suffix}"),
        headers=auth_headers,
    )
    assert issued.status_code == 200, issued.text
    invoice = issued.json()["data"]
    listing = await client.get(
        f"/api/v1/customer-receivables/?invoice_id={invoice['id']}&page_size=100",
        headers=auth_headers,
    )
    assert listing.status_code == 200, listing.text
    rows = listing.json()["data"]["items"]
    assert len(rows) == 1
    return invoice, rows[0]


@pytest.mark.asyncio
async def test_invoice_issuance_creates_one_receivable_snapshot(
    client, auth_headers, test_company, db_session
):
    invoice, receivable = await create_receivable(
        client, auth_headers, test_company, db_session, "CREATE"
    )
    assert receivable["invoice_id"] == invoice["id"]
    assert receivable["invoice_number"] == invoice["invoice_number"]
    assert receivable["client_id"] == invoice["client_id"]
    assert receivable["client_name"] == invoice["client_name"]
    assert receivable["original_amount"] == 212.4
    assert receivable["paid_amount"] == 0
    assert receivable["credited_amount"] == 0
    assert receivable["outstanding_amount"] == 212.4
    assert receivable["status"] == "unpaid"
    assert receivable["due_date"] == invoice["due_date"]

    detail = await client.get(
        f"/api/v1/customer-receivables/{receivable['id']}", headers=auth_headers
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["invoice_id"] == invoice["id"]

    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.company_id == test_company.id,
                AuditLog.action == "customer_receivable.created",
                AuditLog.entity_id == receivable["id"],
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1

    duplicate_issue = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(invoice["order_id"], "AR-CREATE"),
        headers=auth_headers,
    )
    assert duplicate_issue.status_code == 200
    listing = await client.get(
        f"/api/v1/customer-receivables/?invoice_id={invoice['id']}&page_size=100",
        headers=auth_headers,
    )
    assert len(listing.json()["data"]["items"]) == 1


@pytest.mark.asyncio
async def test_customer_payments_are_idempotent_and_reversible(
    client, auth_headers, test_company, db_session
):
    _, receivable = await create_receivable(
        client, auth_headers, test_company, db_session, "PAYMENT"
    )
    payload = {
        "idempotency_key": "customer-payment-one",
        "amount": 50,
        "payment_date": date.today().isoformat(),
        "payment_method": "bank_transfer",
        "reference": "CLIENT-PAY-001",
        "notes": "ნაწილობრივი გადახდა",
    }
    first = await client.post(
        f"/api/v1/customer-receivables/{receivable['id']}/payments",
        json=payload,
        headers=auth_headers,
    )
    assert first.status_code == 200, first.text
    result = first.json()["data"]
    assert result["receivable"]["paid_amount"] == 50
    assert result["receivable"]["outstanding_amount"] == 162.4
    assert result["receivable"]["status"] == "partially_paid"
    payment = result["payment"]

    duplicate = await client.post(
        f"/api/v1/customer-receivables/{receivable['id']}/payments",
        json=payload,
        headers=auth_headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["payment"]["id"] == payment["id"]

    changed_replay = await client.post(
        f"/api/v1/customer-receivables/{receivable['id']}/payments",
        json={**payload, "amount": 49.99},
        headers=auth_headers,
    )
    assert changed_replay.status_code == 409

    overpayment = await client.post(
        f"/api/v1/customer-receivables/{receivable['id']}/payments",
        json={**payload, "idempotency_key": "customer-payment-over", "amount": 162.41},
        headers=auth_headers,
    )
    assert overpayment.status_code == 409

    full = await client.post(
        f"/api/v1/customer-receivables/{receivable['id']}/payments",
        json={**payload, "idempotency_key": "customer-payment-final", "amount": 162.4},
        headers=auth_headers,
    )
    assert full.status_code == 200, full.text
    assert full.json()["data"]["receivable"]["status"] == "paid"

    reversal = await client.post(
        f"/api/v1/customer-payments/{payment['id']}/reversal",
        json={"idempotency_key": "customer-payment-reversal-one", "reason": "არასწორი ჩარიცხვა"},
        headers=auth_headers,
    )
    assert reversal.status_code == 200, reversal.text
    reversed_result = reversal.json()["data"]
    assert reversed_result["payment"]["status"] == "reversed"
    assert reversed_result["receivable"]["paid_amount"] == 162.4
    assert reversed_result["receivable"]["outstanding_amount"] == 50

    duplicate_reversal = await client.post(
        f"/api/v1/customer-payments/{payment['id']}/reversal",
        json={"idempotency_key": "customer-payment-reversal-one", "reason": "არასწორი ჩარიცხვა"},
        headers=auth_headers,
    )
    assert duplicate_reversal.status_code == 200
    second_reversal = await client.post(
        f"/api/v1/customer-payments/{payment['id']}/reversal",
        json={"idempotency_key": "customer-payment-reversal-two", "reason": "მეორე მცდელობა"},
        headers=auth_headers,
    )
    assert second_reversal.status_code == 409


@pytest.mark.asyncio
async def test_customer_credit_note_reduces_outstanding_and_blocks_overcredit(
    client, auth_headers, test_company, db_session
):
    _, receivable = await create_receivable(
        client, auth_headers, test_company, db_session, "CREDIT"
    )
    payload = {
        "idempotency_key": "customer-credit-one",
        "credit_note_number": "CN-CUSTOMER-001",
        "amount": 12.4,
        "credit_date": date.today().isoformat(),
        "reason": "ფასის კორექტირება",
    }
    credited = await client.post(
        f"/api/v1/customer-receivables/{receivable['id']}/credit-notes",
        json=payload,
        headers=auth_headers,
    )
    assert credited.status_code == 200, credited.text
    result = credited.json()["data"]
    assert result["receivable"]["credited_amount"] == 12.4
    assert result["receivable"]["outstanding_amount"] == 200
    assert result["credit_note"]["credit_note_number"] == "CN-CUSTOMER-001"

    duplicate = await client.post(
        f"/api/v1/customer-receivables/{receivable['id']}/credit-notes",
        json=payload,
        headers=auth_headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["credit_note"]["id"] == result["credit_note"]["id"]

    changed_replay = await client.post(
        f"/api/v1/customer-receivables/{receivable['id']}/credit-notes",
        json={**payload, "amount": 12.41},
        headers=auth_headers,
    )
    assert changed_replay.status_code == 409

    overcredit = await client.post(
        f"/api/v1/customer-receivables/{receivable['id']}/credit-notes",
        json={
            **payload,
            "idempotency_key": "customer-credit-over",
            "credit_note_number": "CN-CUSTOMER-OVER",
            "amount": 200.01,
        },
        headers=auth_headers,
    )
    assert overcredit.status_code == 409


@pytest.mark.asyncio
async def test_credit_bank_reconciliation_and_reversal_restore_balances(
    client, auth_headers, test_company, db_session
):
    _, receivable = await create_receivable(
        client, auth_headers, test_company, db_session, "BANK"
    )
    account = await create_bank_account(client, auth_headers, "CUSTOMER")
    await import_statement(client, auth_headers, account["id"], "CUSTOMER")
    transactions = await client.get(
        f"/api/v1/bank-transactions/?bank_account_id={account['id']}&direction=credit",
        headers=auth_headers,
    )
    transaction = transactions.json()["data"]["items"][0]
    payload = {
        "idempotency_key": "customer-bank-match-one",
        "customer_receivable_id": receivable["id"],
        "amount": 100,
        "notes": "კლიენტის ჩარიცხვის შეჯერება",
    }
    matched = await client.post(
        f"/api/v1/bank-transactions/{transaction['id']}/customer-reconciliations",
        json=payload,
        headers=auth_headers,
    )
    assert matched.status_code == 200, matched.text
    result = matched.json()["data"]
    assert result["transaction"]["matched_amount"] == 100
    assert result["transaction"]["unmatched_amount"] == 25.1
    assert result["receivable"]["paid_amount"] == 100
    assert result["receivable"]["outstanding_amount"] == 112.4
    reconciliation = result["reconciliation"]

    history = await client.get(
        f"/api/v1/bank-customer-reconciliations/?customer_receivable_id={receivable['id']}",
        headers=auth_headers,
    )
    assert history.status_code == 200, history.text
    assert history.json()["data"]["total"] == 1
    assert history.json()["data"]["items"][0]["id"] == reconciliation["id"]
    assert history.json()["data"]["items"][0]["status"] == "active"

    duplicate = await client.post(
        f"/api/v1/bank-transactions/{transaction['id']}/customer-reconciliations",
        json=payload,
        headers=auth_headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["reconciliation"]["id"] == reconciliation["id"]

    changed_replay = await client.post(
        f"/api/v1/bank-transactions/{transaction['id']}/customer-reconciliations",
        json={**payload, "amount": 99.99},
        headers=auth_headers,
    )
    assert changed_replay.status_code == 409

    reversed_response = await client.post(
        f"/api/v1/bank-customer-reconciliations/{reconciliation['id']}/reversal",
        json={"idempotency_key": "customer-bank-reversal-one", "reason": "არასწორი კლიენტი"},
        headers=auth_headers,
    )
    assert reversed_response.status_code == 200, reversed_response.text
    reversed_result = reversed_response.json()["data"]
    assert reversed_result["transaction"]["matched_amount"] == 0
    assert reversed_result["receivable"]["paid_amount"] == 0
    assert reversed_result["receivable"]["outstanding_amount"] == 212.4
    assert reversed_result["reconciliation"]["status"] == "reversed"

    reversal_table = await db_session.scalar(
        text("SELECT to_regclass('public.customer_bank_reconciliation_reversals')")
    )
    assert reversal_table == "customer_bank_reconciliation_reversals"

    parent = (
        await db_session.execute(
            text("""
                SELECT status, reversal_idempotency_key, reversal_reason, reversed_by, reversed_at
                FROM customer_bank_reconciliations
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": reconciliation["id"]},
        )
    ).mappings().one()
    assert parent["status"] == "active"
    assert parent["reversal_idempotency_key"] is None
    assert parent["reversal_reason"] is None
    assert parent["reversed_by"] is None
    assert parent["reversed_at"] is None

    reversal_rows = (
        await db_session.execute(
            text("""
                SELECT reconciliation_id, bank_transaction_id, customer_receivable_id,
                       amount, idempotency_key, reason, reversed_by, created_at
                FROM customer_bank_reconciliation_reversals
                WHERE reconciliation_id = CAST(:id AS uuid)
            """),
            {"id": reconciliation["id"]},
        )
    ).mappings().all()
    assert len(reversal_rows) == 1
    reversal_row = reversal_rows[0]
    assert str(reversal_row["bank_transaction_id"]) == transaction["id"]
    assert str(reversal_row["customer_receivable_id"]) == receivable["id"]
    assert reversal_row["amount"] == 100
    assert reversal_row["idempotency_key"] == "customer-bank-reversal-one"
    assert reversal_row["reason"] == "არასწორი კლიენტი"
    assert reversal_row["reversed_by"] is not None
    assert reversal_row["created_at"] is not None

    duplicate_reversal = await client.post(
        f"/api/v1/bank-customer-reconciliations/{reconciliation['id']}/reversal",
        json={"idempotency_key": "customer-bank-reversal-one", "reason": "არასწორი კლიენტი"},
        headers=auth_headers,
    )
    assert duplicate_reversal.status_code == 200
    reversal_count = await db_session.scalar(
        text("""
            SELECT count(*)
            FROM customer_bank_reconciliation_reversals
            WHERE reconciliation_id = CAST(:id AS uuid)
        """),
        {"id": reconciliation["id"]},
    )
    assert reversal_count == 1

    reversed_history = await client.get(
        f"/api/v1/bank-customer-reconciliations/?customer_receivable_id={receivable['id']}&status=reversed",
        headers=auth_headers,
    )
    assert reversed_history.status_code == 200
    assert reversed_history.json()["data"]["total"] == 1
    history_row = reversed_history.json()["data"]["items"][0]
    assert history_row["status"] == "reversed"
    assert history_row["reversal_reason"] == "არასწორი კლიენტი"
    assert history_row["reversed_at"] is not None

    active_history = await client.get(
        f"/api/v1/bank-customer-reconciliations/?customer_receivable_id={receivable['id']}&status=active",
        headers=auth_headers,
    )
    assert active_history.status_code == 200
    assert active_history.json()["data"]["total"] == 0

    second_reversal = await client.post(
        f"/api/v1/bank-customer-reconciliations/{reconciliation['id']}/reversal",
        json={"idempotency_key": "customer-bank-reversal-two", "reason": "მეორე მცდელობა"},
        headers=auth_headers,
    )
    assert second_reversal.status_code == 409


@pytest.mark.asyncio
async def test_customer_finance_mutations_require_finance_role(
    client, auth_headers, test_company, db_session
):
    _, receivable = await create_receivable(
        client, auth_headers, test_company, db_session, "ROLE"
    )
    employee_headers = await create_user_headers(
        client,
        db_session,
        test_company.id,
        "customer-finance-employee@test.ge",
        User.Role.EMPLOYEE,
    )
    forbidden = await client.post(
        f"/api/v1/customer-receivables/{receivable['id']}/payments",
        json={
            "idempotency_key": "forbidden-customer-payment",
            "amount": 1,
            "payment_date": date.today().isoformat(),
            "payment_method": "cash",
        },
        headers=employee_headers,
    )
    assert forbidden.status_code == 403

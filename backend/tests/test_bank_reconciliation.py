from datetime import date

import pytest

from app.models.user import User
from tests.test_supplier_credit_reversals import (
    create_approved_payable,
    create_user_headers,
)


async def create_bank_account(client, auth_headers, suffix: str = "MAIN"):
    response = await client.post(
        "/api/v1/bank-accounts/",
        json={
            "bank_name": "Test Bank",
            "account_name": f"Operating {suffix}",
            "iban": f"GE00TB0000000000{suffix}",
            "currency": "GEL",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def import_statement(client, auth_headers, account_id: str, suffix: str = "ONE"):
    csv_content = (
        "transaction_date,reference,description,counterparty,amount,direction,currency\n"
        f"{date.today()},BANK-{suffix}-1,Supplier payment,Supplier One,60.25,debit,GEL\n"
        f"{date.today()},BANK-{suffix}-2,Client receipt,Client One,125.10,credit,GEL\n"
    )
    response = await client.post(
        f"/api/v1/bank-accounts/{account_id}/statement-imports",
        json={
            "idempotency_key": f"statement-{suffix}",
            "filename": f"statement-{suffix}.csv",
            "csv_content": csv_content,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"], csv_content


@pytest.mark.asyncio
async def test_bank_account_and_csv_import_are_tenant_scoped_and_idempotent(
    client, auth_headers, test_company, db_session
):
    account = await create_bank_account(client, auth_headers)
    imported, csv_content = await import_statement(client, auth_headers, account["id"])

    assert imported["filename"] == "statement-ONE.csv"
    assert imported["transaction_count"] == 2
    assert imported["debit_total"] == 60.25
    assert imported["credit_total"] == 125.10

    duplicate = await client.post(
        f"/api/v1/bank-accounts/{account['id']}/statement-imports",
        json={
            "idempotency_key": "statement-ONE",
            "filename": "statement-ONE.csv",
            "csv_content": csv_content,
        },
        headers=auth_headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["id"] == imported["id"]

    transactions = await client.get(
        f"/api/v1/bank-transactions/?bank_account_id={account['id']}",
        headers=auth_headers,
    )
    assert transactions.status_code == 200, transactions.text
    rows = transactions.json()["data"]["items"]
    assert len(rows) == 2
    debit = next(row for row in rows if row["direction"] == "debit")
    assert debit["amount"] == 60.25
    assert debit["matched_amount"] == 0
    assert debit["unmatched_amount"] == 60.25
    assert debit["status"] == "unmatched"

    employee_headers = await create_user_headers(
        client,
        db_session,
        test_company.id,
        "bank-employee@test.ge",
        User.Role.EMPLOYEE,
    )
    forbidden = await client.post(
        "/api/v1/bank-accounts/",
        json={
            "bank_name": "Forbidden Bank",
            "account_name": "No Access",
            "iban": "GE00NOACCESS0000001",
            "currency": "GEL",
        },
        headers=employee_headers,
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_debit_reconciliation_posts_supplier_payment_and_prevents_overmatch(
    client, auth_headers, test_company, db_session
):
    payable = await create_approved_payable(
        client, auth_headers, test_company, db_session, "BANK-MATCH"
    )
    account = await create_bank_account(client, auth_headers, "MATCH")
    await import_statement(client, auth_headers, account["id"], "MATCH")
    transactions = await client.get(
        f"/api/v1/bank-transactions/?bank_account_id={account['id']}&direction=debit",
        headers=auth_headers,
    )
    transaction = transactions.json()["data"]["items"][0]

    payload = {
        "idempotency_key": "reconcile-bank-match",
        "supplier_payable_id": payable["id"],
        "amount": 40.25,
        "notes": "Matched from bank statement",
    }
    reconciled = await client.post(
        f"/api/v1/bank-transactions/{transaction['id']}/reconciliations",
        json=payload,
        headers=auth_headers,
    )
    assert reconciled.status_code == 200, reconciled.text
    result = reconciled.json()["data"]
    assert result["transaction"]["matched_amount"] == 40.25
    assert result["transaction"]["unmatched_amount"] == 20
    assert result["transaction"]["status"] == "partially_matched"
    assert result["payable"]["paid_amount"] == 40.25
    assert result["payable"]["outstanding_amount"] == 59.75
    assert result["reconciliation"]["status"] == "active"

    duplicate = await client.post(
        f"/api/v1/bank-transactions/{transaction['id']}/reconciliations",
        json=payload,
        headers=auth_headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["reconciliation"]["id"] == result["reconciliation"]["id"]

    overmatch = await client.post(
        f"/api/v1/bank-transactions/{transaction['id']}/reconciliations",
        json={**payload, "idempotency_key": "reconcile-overmatch", "amount": 20.01},
        headers=auth_headers,
    )
    assert overmatch.status_code == 409


@pytest.mark.asyncio
async def test_reconciliation_reversal_restores_bank_and_payable_balances(
    client, auth_headers, test_company, db_session
):
    payable = await create_approved_payable(
        client, auth_headers, test_company, db_session, "BANK-REVERSE"
    )
    account = await create_bank_account(client, auth_headers, "REVERSE")
    await import_statement(client, auth_headers, account["id"], "REVERSE")
    transactions = await client.get(
        f"/api/v1/bank-transactions/?bank_account_id={account['id']}&direction=debit",
        headers=auth_headers,
    )
    transaction = transactions.json()["data"]["items"][0]
    reconciled = await client.post(
        f"/api/v1/bank-transactions/{transaction['id']}/reconciliations",
        json={
            "idempotency_key": "reconcile-to-reverse",
            "supplier_payable_id": payable["id"],
            "amount": 60.25,
            "notes": "Full bank match",
        },
        headers=auth_headers,
    )
    assert reconciled.status_code == 200, reconciled.text
    reconciliation = reconciled.json()["data"]["reconciliation"]

    reversed_response = await client.post(
        f"/api/v1/bank-reconciliations/{reconciliation['id']}/reversal",
        json={
            "idempotency_key": "bank-reversal-one",
            "reason": "არასწორ payable-ზე იყო მიბმული",
        },
        headers=auth_headers,
    )
    assert reversed_response.status_code == 200, reversed_response.text
    result = reversed_response.json()["data"]
    assert result["reconciliation"]["status"] == "reversed"
    assert result["transaction"]["matched_amount"] == 0
    assert result["transaction"]["unmatched_amount"] == 60.25
    assert result["transaction"]["status"] == "unmatched"
    assert result["payable"]["paid_amount"] == 0
    assert result["payable"]["outstanding_amount"] == 100

    duplicate = await client.post(
        f"/api/v1/bank-reconciliations/{reconciliation['id']}/reversal",
        json={
            "idempotency_key": "bank-reversal-one",
            "reason": "არასწორ payable-ზე იყო მიბმული",
        },
        headers=auth_headers,
    )
    assert duplicate.status_code == 200

    second = await client.post(
        f"/api/v1/bank-reconciliations/{reconciliation['id']}/reversal",
        json={"idempotency_key": "bank-reversal-two", "reason": "მეორე მცდელობა"},
        headers=auth_headers,
    )
    assert second.status_code == 409

    history = await client.get(
        f"/api/v1/bank-reconciliations/?bank_transaction_id={transaction['id']}",
        headers=auth_headers,
    )
    assert history.status_code == 200, history.text
    rows = history.json()["data"]["items"]
    assert len(rows) == 1
    assert rows[0]["status"] == "reversed"
    assert rows[0]["transaction_reference"] == transaction["reference"]
    assert rows[0]["supplier_name"]
    assert rows[0]["supplier_invoice_number"]

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.services.accounting_periods import AccountingPeriodClosedError
from app.services.gl_posting import post_journal_entry
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_close_list_and_reopen_accounting_period(client, auth_headers):
    closed = await client.post(
        "/api/v1/accounting-periods/2026/7/close",
        headers=auth_headers,
        json={"reason": "ივლისის დახურვა"},
    )
    assert closed.status_code == 200
    assert closed.json()["data"]["status"] == "closed"
    assert closed.json()["data"]["year"] == 2026
    assert closed.json()["data"]["month"] == 7

    periods = await client.get(
        "/api/v1/accounting-periods?year=2026",
        headers=auth_headers,
    )
    assert periods.status_code == 200
    assert len(periods.json()["data"]) == 1
    assert periods.json()["data"][0]["status"] == "closed"

    reopened = await client.post(
        "/api/v1/accounting-periods/2026/7/reopen",
        headers=auth_headers,
        json={"reason": "კორექტირების საჭიროება"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["data"]["status"] == "open"


@pytest.mark.asyncio
async def test_closed_period_blocks_gl_posting(client, auth_headers, test_admin):
    closed = await client.post(
        "/api/v1/accounting-periods/2026/7/close",
        headers=auth_headers,
        json={"reason": "ივლისის საბოლოო დახურვა"},
    )
    assert closed.status_code == 200

    async with TestSessionLocal() as session:
        with pytest.raises(AccountingPeriodClosedError):
            await post_journal_entry(
                session,
                test_admin.company_id,
                test_admin,
                entry_date=date(2026, 7, 15),
                description="დახურული პერიოდის სატესტო გატარება",
                reference_type="period_lock_test",
                reference_id=uuid4(),
                lines=[
                    ("1410", Decimal("10.00"), Decimal("0.00")),
                    ("4100", Decimal("0.00"), Decimal("10.00")),
                ],
            )
        await session.rollback()


@pytest.mark.asyncio
async def test_closed_period_blocks_cash_transaction_without_changing_balance(client, auth_headers):
    account_response = await client.post(
        "/api/v1/cash/accounts",
        headers=auth_headers,
        json={"name": "მთავარი სალარო", "currency": "GEL"},
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["data"]["id"]

    closed = await client.post(
        "/api/v1/accounting-periods/2026/7/close",
        headers=auth_headers,
        json={"reason": "ივლისის საბოლოო დახურვა"},
    )
    assert closed.status_code == 200

    transaction = await client.post(
        f"/api/v1/cash/accounts/{account_id}/transactions",
        headers=auth_headers,
        json={
            "cash_account_id": account_id,
            "transaction_date": "2026-07-15",
            "direction": "inflow",
            "amount": "100.00",
            "category": "other",
            "description": "დახურული პერიოდის ოპერაცია",
        },
    )
    assert transaction.status_code == 409

    accounts = await client.get("/api/v1/cash/accounts", headers=auth_headers)
    account = next(row for row in accounts.json()["data"] if row["id"] == account_id)
    assert account["balance"] == 0.0


@pytest.mark.asyncio
async def test_closed_period_blocks_expense_creation(client, auth_headers):
    await client.post(
        "/api/v1/accounting-periods/2026/7/close",
        headers=auth_headers,
        json={"reason": "ივლისის დახურვა"},
    )
    response = await client.post(
        "/api/v1/expenses/",
        headers=auth_headers,
        json={
            "expense_date": "2026-07-10",
            "description": "დახურული პერიოდის ხარჯი",
            "amount": "25.00",
            "currency": "GEL",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_closed_period_blocks_asset_creation(client, auth_headers):
    await client.post(
        "/api/v1/accounting-periods/2026/7/close",
        headers=auth_headers,
        json={"reason": "ივლისის დახურვა"},
    )
    response = await client.post(
        "/api/v1/assets/",
        headers=auth_headers,
        json={
            "name": "სატესტო კომპიუტერი",
            "asset_type": "equipment",
            "purchase_date": "2026-07-05",
            "purchase_cost": "1200.00",
            "useful_life_years": 3,
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_closed_period_blocks_analytic_entry_creation(client, auth_headers):
    account_response = await client.post(
        "/api/v1/analytic/accounts",
        headers=auth_headers,
        json={"code": "CC-LOCK", "name": "ჩაკეტვის ტესტი"},
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["data"]["id"]
    await client.post(
        "/api/v1/accounting-periods/2026/7/close",
        headers=auth_headers,
        json={"reason": "ივლისის დახურვა"},
    )
    response = await client.post(
        "/api/v1/analytic/entries",
        headers=auth_headers,
        json={
            "analytic_account_id": account_id,
            "entry_date": "2026-07-08",
            "description": "დახურული პერიოდის ანალიტიკა",
            "amount": "15.00",
            "direction": "expense",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_closed_period_blocks_bank_statement_import(client, auth_headers):
    account_response = await client.post(
        "/api/v1/bank-accounts/",
        headers=auth_headers,
        json={
            "bank_name": "Test Bank",
            "account_name": "GEL ანგარიში",
            "iban": "GE00TEST0000000001",
            "currency": "GEL",
        },
    )
    assert account_response.status_code == 200
    account_id = account_response.json()["data"]["id"]
    await client.post(
        "/api/v1/accounting-periods/2026/7/close",
        headers=auth_headers,
        json={"reason": "ივლისის დახურვა"},
    )
    csv_content = (
        "transaction_date,reference,description,counterparty,amount,direction,currency\n"
        "2026-07-11,LOCK-1,დახურული პერიოდი,Test,50.00,debit,GEL\n"
    )
    response = await client.post(
        f"/api/v1/bank-accounts/{account_id}/statement-imports",
        headers=auth_headers,
        json={
            "idempotency_key": "period-lock-bank-1",
            "filename": "closed.csv",
            "csv_content": csv_content,
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_period_history_keeps_close_and_reopen_events(client, auth_headers):
    closed = await client.post(
        "/api/v1/accounting-periods/2026/7/close",
        headers=auth_headers,
        json={"reason": "ივლისის დახურვა"},
    )
    period_id = closed.json()["data"]["id"]
    await client.post(
        "/api/v1/accounting-periods/2026/7/reopen",
        headers=auth_headers,
        json={"reason": "დადასტურებული კორექტირება"},
    )
    history = await client.get(
        f"/api/v1/accounting-periods/{period_id}/history",
        headers=auth_headers,
    )
    assert history.status_code == 200
    assert [event["action"] for event in history.json()["data"]] == ["closed", "reopened"]


@pytest.mark.asyncio
async def test_accountant_can_close_but_only_admin_can_reopen(client, test_company):
    async with TestSessionLocal() as session:
        accountant = User(
            company_id=test_company.id,
            email="accountant@test.ge",
            hashed_password=hash_password("accountant123"),
            full_name="Test Accountant",
            role=User.Role.ACCOUNTANT,
            is_active=True,
        )
        session.add(accountant)
        await session.commit()
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "accountant@test.ge", "password": "accountant123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    closed = await client.post(
        "/api/v1/accounting-periods/2026/8/close",
        headers=headers,
        json={"reason": "აგვისტოს დახურვა"},
    )
    assert closed.status_code == 200
    reopened = await client.post(
        "/api/v1/accounting-periods/2026/8/reopen",
        headers=headers,
        json={"reason": "დაუშვებელი გახსნა"},
    )
    assert reopened.status_code == 403


@pytest.mark.asyncio
async def test_open_period_allows_cash_transaction_with_complete_response(client, auth_headers):
    account_response = await client.post(
        "/api/v1/cash/accounts",
        headers=auth_headers,
        json={"name": "ღია პერიოდის სალარო", "currency": "GEL"},
    )
    account_id = account_response.json()["data"]["id"]
    transaction = await client.post(
        f"/api/v1/cash/accounts/{account_id}/transactions",
        headers=auth_headers,
        json={
            "cash_account_id": account_id,
            "transaction_date": "2026-09-01",
            "direction": "inflow",
            "amount": "100.00",
            "category": "other",
            "description": "ღია პერიოდის ოპერაცია",
        },
    )
    assert transaction.status_code == 201
    assert transaction.json()["data"]["cash_account_name"] == "ღია პერიოდის სალარო"


@pytest.mark.asyncio
async def test_cash_account_with_transaction_history_cannot_be_hard_deleted(client, auth_headers):
    account_response = await client.post(
        "/api/v1/cash/accounts",
        headers=auth_headers,
        json={"name": "ისტორიის სალარო", "currency": "GEL"},
    )
    account_id = account_response.json()["data"]["id"]
    created = await client.post(
        f"/api/v1/cash/accounts/{account_id}/transactions",
        headers=auth_headers,
        json={
            "cash_account_id": account_id,
            "transaction_date": "2026-09-01",
            "direction": "inflow",
            "amount": "10.00",
            "category": "other",
            "description": "ისტორიის დაცვის ტესტი",
        },
    )
    assert created.status_code == 201
    deleted = await client.delete(f"/api/v1/cash/accounts/{account_id}", headers=auth_headers)
    assert deleted.status_code == 409


@pytest.mark.asyncio
async def test_asset_with_depreciation_history_cannot_be_hard_deleted(client, auth_headers):
    asset_response = await client.post(
        "/api/v1/assets/",
        headers=auth_headers,
        json={
            "name": "ისტორიის აქტივი",
            "asset_type": "equipment",
            "purchase_date": "2026-06-01",
            "purchase_cost": "1200.00",
            "useful_life_years": 3,
        },
    )
    assert asset_response.status_code == 201
    asset_id = asset_response.json()["data"]["id"]
    depreciation = await client.post(f"/api/v1/assets/{asset_id}/run-depreciation", headers=auth_headers)
    assert depreciation.status_code == 200
    deleted = await client.delete(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert deleted.status_code == 409

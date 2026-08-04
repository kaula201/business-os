"""Tests for the SRS (Georgian tax reporting) module."""
from datetime import date

import pytest
from sqlalchemy import select

from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.invoice import Invoice
from app.models.order import Order


@pytest.mark.asyncio
async def test_srs_status_reports_gl_ready(client, auth_headers, test_company):
    resp = await client.get("/api/v1/srs/status", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["gl_ready"] is True
    assert data["vat_enabled"] is True
    assert data["income_tax_enabled"] is True
    assert data["balance_form_enabled"] is True


@pytest.mark.asyncio
async def test_srs_reconciliation_balanced_for_empty_period(
    client, auth_headers, test_company, db_session
):
    now = date.today()
    resp = await client.get(
        f"/api/v1/srs/reconciliation?year={now.year}&month={now.month}",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["is_balanced"] is True
    assert data["difference"] == 0.0
    assert data["journal_entries_count"] == 0


@pytest.mark.asyncio
async def test_srs_vat_declaration_and_income_tax_exist(
    client, auth_headers, test_company
):
    now = date.today()
    vat = await client.get(
        f"/api/v1/srs/vat-declaration?year={now.year}&month={now.month}",
        headers=auth_headers,
    )
    assert vat.status_code == 200, vat.text
    assert vat.json()["data"]["net_vat"] is not None

    tax = await client.get(
        f"/api/v1/srs/income-tax?year={now.year}&month={now.month}",
        headers=auth_headers,
    )
    assert tax.status_code == 200, tax.text
    assert tax.json()["data"]["taxable_profit"] is not None


@pytest.mark.asyncio
async def test_srs_balance_form_balances(
    client, auth_headers, test_company, db_session
):
    """Balance form: total assets should equal liabilities + equity."""

    # Create a simple balanced journal entry via GL accounts directly.
    accounts = (
        await db_session.execute(
            select(GLAccount).where(GLAccount.company_id == test_company.id)
        )
    ).scalars().all()
    assert accounts, "test_company must seed default GL accounts"
    # First asset (1xxx) and first equity (3xxx) account
    asset = next((a for a in accounts if a.code.startswith("1")), accounts[0])
    equity = next((a for a in accounts if a.code.startswith("3")), accounts[0])

    je = JournalEntry(
        company_id=test_company.id,
        entry_number=f"JE-TEST-{test_company.id.hex[:6]}",
        entry_date=date.today(),
        reference_type="manual",
        reference_id=test_company.id,
        description="test",
    )
    db_session.add(je)
    await db_session.flush()
    db_session.add_all([
        JournalEntryLine(journal_entry_id=je.id, gl_account_id=asset.id, line_number=1, debit_amount=100, credit_amount=0),
        JournalEntryLine(journal_entry_id=je.id, gl_account_id=equity.id, line_number=2, debit_amount=0, credit_amount=100),
    ])
    await db_session.commit()

    resp = await client.get(
        "/api/v1/srs/balance-form",
        params={"as_of_date": str(date.today())},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert abs(data["total_assets"] - (data["total_liabilities"] + data["total_equity"])) < 0.01

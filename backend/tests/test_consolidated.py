"""Tests for consolidated (multi-company) accounting reports."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.accounting_controls import ConsolidationAccountMapping, FxTranslationRate
from app.models.company import Company
from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.user import User
from app.core.security import hash_password
from app.services.gl_posting import seed_default_accounts
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _setup_grouped_company(session, name: str, code: str, group_id: uuid.UUID) -> Company:
    company = Company(
        name=name, identification_code=code, vat_status=False,
        currency="GEL", company_group_id=group_id,
    )
    session.add(company)
    await session.flush()
    await seed_default_accounts(session, company.id)
    return company


async def _post_pl_entry(session, company: Company, income: Decimal, expense: Decimal, on_date: date):
    """Simple P&L entry: income (4100) credit, expense (5200) debit, bank (1410) mirror."""
    accounts = (
        await session.execute(select(GLAccount).where(GLAccount.company_id == company.id))
    ).scalars().all()
    acc = {a.code: a.id for a in accounts}
    entry = JournalEntry(
        company_id=company.id,
        entry_number=f"CONS-{company.identification_code}-{uuid.uuid4().hex[:6]}",
        entry_date=on_date,
        description=f"Consolidated test {company.name}",
        reference_type="manual",
        reference_id=uuid.uuid4(),
    )
    session.add(entry)
    await session.flush()
    session.add(JournalEntryLine(journal_entry_id=entry.id, gl_account_id=acc["4100"], line_number=1,
                                 debit_amount=0, credit_amount=income, description="income"))
    session.add(JournalEntryLine(journal_entry_id=entry.id, gl_account_id=acc["5200"], line_number=2,
                                 debit_amount=expense, credit_amount=0, description="expense"))
    session.add(JournalEntryLine(journal_entry_id=entry.id, gl_account_id=acc["1410"], line_number=3,
                                 debit_amount=income - expense if income >= expense else 0,
                                 credit_amount=expense - income if expense > income else 0,
                                 description="bank"))
    await session.commit()


async def _create_admin(db_session, company_id: uuid.UUID, email: str) -> User:
    user = User(
        company_id=company_id,
        email=email,
        hashed_password=hash_password("admin123"),
        full_name="Cons Admin",
        role=User.Role.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "admin123"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_consolidated_pl_sums_two_companies(client, auth_headers, test_company, db_session):
    group = uuid.uuid4()
    async with TestSessionLocal() as session:
        co_a = await _setup_grouped_company(session, "Alpha", "CONS-A", group)
        co_b = await _setup_grouped_company(session, "Beta", "CONS-B", group)
        # Put test_company into the same group too
        tc = (await session.execute(select(Company).where(Company.id == test_company.id))).scalar_one()
        tc.company_group_id = group
        await session.commit()
        # entries: A income 1000 expense 400; B income 500 expense 100
        await _post_pl_entry(session, co_a, Decimal("1000"), Decimal("400"), date(2026, 8, 5))
        await _post_pl_entry(session, co_b, Decimal("500"), Decimal("100"), date(2026, 8, 6))

    resp = await client.get("/api/v1/gl/consolidated/profit-loss", params={
        "date_from": "2026-08-01", "date_to": "2026-08-31",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total_income"] == 1500.0
    assert data["total_expenses"] == 500.0
    assert data["net_income"] == 1000.0
    assert len(data["companies"]) == 3


async def test_consolidated_bs_aggregates_assets(client, auth_headers, test_company, db_session):
    group = uuid.uuid4()
    async with TestSessionLocal() as session:
        co_a = await _setup_grouped_company(session, "Alpha", "CONS-C", group)
        tc = (await session.execute(select(Company).where(Company.id == test_company.id))).scalar_one()
        tc.company_group_id = group
        await session.commit()
        await _post_pl_entry(session, co_a, Decimal("1000"), Decimal("400"), date(2026, 8, 5))

    resp = await client.get("/api/v1/gl/consolidated/balance-sheet", params={
        "as_of_date": "2026-08-31",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # Bank (1410) has 600 from the P&L entry: asset total >= 600
    assert data["total_assets"] >= 600.0
    assert data["net_income_included"] == 600.0


async def test_consolidated_bs_balances_across_periods(client, auth_headers, test_company, db_session):
    """Invariant: A = L + E even when income spans multiple months (P0 regression)."""
    group = uuid.uuid4()
    async with TestSessionLocal() as session:
        co_a = await _setup_grouped_company(session, "Alpha", "CONS-BAL", group)
        tc = (await session.execute(select(Company).where(Company.id == test_company.id))).scalar_one()
        tc.company_group_id = group
        await session.commit()
        # July income 500 (asset 590 / VAT 90), August income 100 (bank 118 / VAT 18)
        await _post_pl_entry(session, co_a, Decimal("500"), Decimal("0"), date(2026, 7, 24))
        await _post_pl_entry(session, co_a, Decimal("100"), Decimal("0"), date(2026, 8, 19))

    resp = await client.get("/api/v1/gl/consolidated/balance-sheet", params={
        "as_of_date": "2026-08-31",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # The full historical net income (600) must be in equity — not just August's 100
    assert data["net_income_included"] == 600.0
    diff = round(data["total_assets"] - data["total_liabilities"] - data["total_equity"], 2)
    assert diff == 0.0, f"Balance sheet out of balance by {diff}"


async def test_consolidated_scope_is_group_only(client, auth_headers, test_company, db_session):
    # A company in a different group must NOT be included
    group = uuid.uuid4()
    other_group = uuid.uuid4()
    async with TestSessionLocal() as session:
        co_a = await _setup_grouped_company(session, "Alpha", "CONS-D", group)
        co_z = await _setup_grouped_company(session, "Zeta", "CONS-Z", other_group)
        tc = (await session.execute(select(Company).where(Company.id == test_company.id))).scalar_one()
        tc.company_group_id = group
        await session.commit()
        await _post_pl_entry(session, co_a, Decimal("1000"), Decimal("0"), date(2026, 8, 5))
        await _post_pl_entry(session, co_z, Decimal("99999"), Decimal("0"), date(2026, 8, 6))

    resp = await client.get("/api/v1/gl/consolidated/profit-loss", params={
        "date_from": "2026-08-01", "date_to": "2026-08-31",
    }, headers=auth_headers)
    data = resp.json()["data"]
    assert data["total_income"] == 1000.0  # Zeta (99999) excluded
    names = [c["name"] for c in data["companies"]]
    assert "Zeta" not in names


async def test_consolidation_uses_account_mapping(client, auth_headers, test_company):
    group = uuid.uuid4()
    async with TestSessionLocal() as session:
        co_a = await _setup_grouped_company(session, "Mapped Co", "CONS-MAP", group)
        tc = (await session.execute(select(Company).where(Company.id == test_company.id))).scalar_one()
        tc.company_group_id = group
        session.add(ConsolidationAccountMapping(
            company_id=co_a.id, source_account_code="4100", target_account_code="4199",
            target_name="Mapped group revenue", target_account_type="income",
        ))
        await session.commit()
        await _post_pl_entry(session, co_a, Decimal("100"), Decimal("0"), date(2026, 8, 5))

    resp = await client.get("/api/v1/gl/consolidated/profit-loss", params={
        "date_from": "2026-08-01", "date_to": "2026-08-31",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    income = resp.json()["data"]["income_accounts"]
    assert any(row["code"] == "4199" and row["balance"] == 100.0 for row in income)


async def test_consolidation_translates_foreign_currency_with_persisted_rate(client, auth_headers, test_company):
    group = uuid.uuid4()
    async with TestSessionLocal() as session:
        co_a = await _setup_grouped_company(session, "USD Co", "CONS-FX", group)
        co_a.currency = "USD"
        tc = (await session.execute(select(Company).where(Company.id == test_company.id))).scalar_one()
        tc.company_group_id = group
        session.add(FxTranslationRate(
            company_id=co_a.id, target_currency="GEL", rate_date=date(2026, 8, 31),
            rate=Decimal("2.000000"), method="average", source="nbg", is_locked=True,
        ))
        await session.commit()
        await _post_pl_entry(session, co_a, Decimal("500"), Decimal("100"), date(2026, 8, 5))

    missing_currency = await client.get("/api/v1/gl/consolidated/profit-loss", params={
        "date_from": "2026-08-01", "date_to": "2026-08-31",
    }, headers=auth_headers)
    assert missing_currency.status_code == 422

    resp = await client.get("/api/v1/gl/consolidated/profit-loss", params={
        "date_from": "2026-08-01", "date_to": "2026-08-31",
        "presentation_currency": "GEL", "fx_method": "average",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["presentation_currency"] == "GEL"
    assert data["total_income"] == 1000.0
    assert data["total_expenses"] == 200.0
    assert data["net_income"] == 800.0


async def test_intercompany_balances_reconciliation(client, auth_headers, test_company, db_session):
    """Two group companies post to the same account code — the report shows
    per-company balances so A's receivable mirrors B's payable."""
    group = uuid.uuid4()
    async with TestSessionLocal() as session:
        co_a = await _setup_grouped_company(session, "Alpha", "CONS-IC-A", group)
        co_b = await _setup_grouped_company(session, "Beta", "CONS-IC-B", group)
        tc = (await session.execute(select(Company).where(Company.id == test_company.id))).scalar_one()
        tc.company_group_id = group
        await session.commit()

        # A: receivable 300 on 1100 (asset, Dr); B: payable 300 on 2100 (liability, Cr)
        for company, code, amount, on_date in [
            (co_a, "1100", Decimal("300"), date(2026, 8, 10)),
            (co_b, "2100", Decimal("300"), date(2026, 8, 10)),
        ]:
            accounts = (await session.execute(
                select(GLAccount).where(GLAccount.company_id == company.id)
            )).scalars().all()
            acc = {a.code: a.id for a in accounts}
            entry = JournalEntry(
                company_id=company.id,
                entry_number=f"IC-{company.identification_code}-{uuid.uuid4().hex[:6]}",
                entry_date=on_date, description="intercompany test",
                reference_type="manual", reference_id=uuid.uuid4(),
            )
            session.add(entry)
            await session.flush()
            is_liability = code == "2100"
            session.add(JournalEntryLine(journal_entry_id=entry.id, gl_account_id=acc[code], line_number=1,
                                         debit_amount=0 if is_liability else amount,
                                         credit_amount=amount if is_liability else 0, description="ic"))
            session.add(JournalEntryLine(journal_entry_id=entry.id, gl_account_id=acc["1410"], line_number=2,
                                         debit_amount=amount if is_liability else 0,
                                         credit_amount=0 if is_liability else amount, description="bank"))
        await session.commit()

    resp = await client.get("/api/v1/gl/consolidated/intercompany-balances", params={
        "as_of_date": "2026-08-31",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data["companies"]) == 3
    codes = {a["account_code"] for a in data["accounts"]}
    assert "1100" in codes
    assert "2100" in codes
    # Alpha's 1100 balance is +300 (asset)
    for acc in data["accounts"]:
        if acc["account_code"] == "1100":
            assert any(b["balance"] == 300.0 for b in acc["balances"].values())
        if acc["account_code"] == "2100":
            assert any(b["balance"] == 300.0 for b in acc["balances"].values())

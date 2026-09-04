"""Scheduled financial automation — full monthly close for one company."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.assets import AssetDepreciation, FixedAsset
from app.models.deferred import DeferredRecognition, DeferredSchedule
from app.models.gl import GLAccount, JournalEntry
from app.services.financial_automation import run_financial_automation_for_company
from app.services.gl_posting import seed_default_accounts
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed_asset(test_company) -> str:
    async with TestSessionLocal() as s:
        a = FixedAsset(
            company_id=test_company.id, name="Auto Depr Asset", asset_type="equipment",
            purchase_date=date(2026, 1, 1), purchase_cost=Decimal("12000"),
            useful_life_years=5, depreciation_method="straight_line",
            salvage_value=Decimal("0"), book_value=Decimal("12000"), status="active",
        )
        s.add(a)
        await s.commit()
        return str(a.id)


async def _seed_deferred(test_company) -> None:
    async with TestSessionLocal() as s:
        await seed_default_accounts(s, test_company.id)
        source = GLAccount(company_id=test_company.id, code="1560", name="Test Deferred", account_type="asset")
        target = GLAccount(company_id=test_company.id, code="5260", name="Test Expense", account_type="expense")
        s.add_all([source, target])
        await s.flush()
        sched = DeferredSchedule(
            company_id=test_company.id, name="Test Schedule", deferral_type="expense",
            total_amount=Decimal("300"), start_date=date(2026, 7, 1), periods=3,
            source_gl_account_id=source.id, recognition_gl_account_id=target.id,
            status="active",
        )
        s.add(sched)
        await s.flush()
        # two due periods (past months) and one future (next month) — date-agnostic
        # (test was written when today was 2026-08 with Jul/Aug due + Sep future)
        today = date.today()
        # past: two months before current month
        y2, m2 = (today.year - 1, 12) if today.month <= 2 else (today.year, today.month - 2)
        y1, m1 = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
        # future: next month
        yf, mf = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        for i, d in enumerate([date(y2, m2, 1), date(y1, m1, 1), date(yf, mf, 1)], start=1):
            s.add(DeferredRecognition(
                company_id=test_company.id, schedule_id=sched.id, period_no=i,
                recognition_date=d, amount=Decimal("100"), status="pending",
            ))
        await s.commit()


async def test_full_monthly_close(client, auth_headers, test_company, db_session):
    from app.models.user import User
    from app.core.security import hash_password
    async with TestSessionLocal() as s:
        existing = (await s.execute(select(User).where(User.company_id == test_company.id))).scalars().first()
        if not existing:
            s.add(User(
                company_id=test_company.id, email="auto-admin@test.ge",
                hashed_password=hash_password("admin123"), full_name="Auto Admin",
                role=User.Role.ADMIN, is_active=True,
            ))
            await s.commit()

    await seed_default_accounts(db_session, test_company.id)
    await db_session.commit()
    await _seed_asset(test_company)
    await _seed_deferred(test_company)
    # FX rate so the run has something to revalue (no open FX rows → no-op is fine)

    result = await run_financial_automation_for_company(db_session, test_company.id)
    assert "depreciation_posted" in result
    assert result["depreciation_posted"] == 1  # 12000/60 = 200
    assert result["deferred_recognized"] == 2  # two past periods due

    # GL entries created for both
    async with TestSessionLocal() as s:
        dep = (await s.execute(select(AssetDepreciation))).scalars().first()
        assert dep is not None
        assert dep.amount == Decimal("200.00")
        entries = (await s.execute(select(JournalEntry))).scalars().all()
        types = {e.reference_type for e in entries}
        assert "asset_depreciation" in types
        assert "deferred_recognition" in types
        # deferred: future period untouched
        future = (await s.execute(select(DeferredRecognition).where(DeferredRecognition.period_no == 3))).scalar_one()
        assert future.status == "pending"


async def seed_default_rates(company_id, session=None):
    from app.models.currency import CurrencyRate
    async with TestSessionLocal() as s:
        existing = (await s.execute(select(CurrencyRate).where(CurrencyRate.company_id == company_id))).scalars().first()
        if not existing:
            s.add(CurrencyRate(
                company_id=company_id, from_currency="USD", to_currency="GEL",
                rate_date=date(2026, 8, 1), rate=Decimal("2.7"), source="manual",
            ))
            await s.commit()

"""Tests for exchange differences (revaluation of open foreign-currency receivables)."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.currency import CurrencyRate
from app.models.exchange_difference import ExchangeDifference
from app.models.gl import JournalEntry, JournalEntryLine
from app.models.receivable import CustomerReceivable
from app.services.exchange_differences import run_revaluation
from app.services.gl_posting import seed_default_accounts
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed_accounts(test_company) -> dict[str, str]:
    async with TestSessionLocal() as session:
        await seed_default_accounts(session, test_company.id)
        await session.commit()
    # fetch ids
    from app.models.gl import GLAccount
    async with TestSessionLocal() as session:
        rows = (await session.execute(select(GLAccount).where(GLAccount.company_id == test_company.id))).scalars().all()
        return {a.code: str(a.id) for a in rows}


async def _create_usd_receivable(client, auth_headers, test_company, amount=Decimal("100.00")) -> str:
    """Create an open USD receivable directly in DB (orders are GEL-only)."""
    from app.models.client import Client
    from app.models.invoice import Invoice
    from app.models.order import Order

    async with TestSessionLocal() as session:
        cust = Client(
            company_id=test_company.id,
            name="FX Client",
            client_type="legal",
            identification_code="FX-001",
            vat_status=False,
            status="active",
        )
        session.add(cust)
        await session.flush()
        order = Order(
            company_id=test_company.id,
            client_id=cust.id,
            order_number=f"ORD-FX-{uuid.uuid4().hex[:8]}",
            status="confirmed",
            subtotal=float(amount),
            vat_amount=0,
            total=float(amount),
        )
        session.add(order)
        await session.flush()
        invoice = Invoice(
            company_id=test_company.id,
            client_id=cust.id,
            order_id=order.id,
            invoice_number="INV-FX-001",
            idempotency_key=f"fx-{uuid.uuid4().hex[:8]}",
            status="issued",
            invoice_date=date(2026, 8, 1),
            due_date=date(2026, 9, 1),
            currency="USD",
            subtotal=amount,
            vat_amount=Decimal("0"),
            total=amount,
            order_number=order.order_number,
            seller_name="Test Company",
            seller_identification_code="TEST-001",
            client_name="FX Client",
            client_identification_code="FX-001",
        )
        session.add(invoice)
        await session.flush()
        rec = CustomerReceivable(
            company_id=test_company.id,
            invoice_id=invoice.id,
            client_id=cust.id,
            invoice_number="INV-FX-001",
            client_name="FX Client",
            currency="USD",
            original_amount=amount,
            paid_amount=Decimal("0"),
            credited_amount=Decimal("0"),
            outstanding_amount=amount,
            due_date=date(2026, 9, 1),
            status="unpaid",
        )
        session.add(rec)
        await session.commit()
        return str(rec.id)


async def _add_rate(test_company, currency: str, rate: str, on_date: date):
    async with TestSessionLocal() as session:
        session.add(CurrencyRate(
            company_id=test_company.id,
            from_currency=currency,
            to_currency="GEL",
            rate_date=on_date,
            rate=Decimal(rate),
            source="manual",
        ))
        await session.commit()


# ── Revaluation run ──────────────────────────────────────────────────────────


async def test_revaluation_posts_gain_entry(client: AsyncClient, auth_headers, test_company):
    await _seed_accounts(test_company)
    rec_id = await _create_usd_receivable(client, auth_headers, test_company, Decimal("100.00"))
    await _add_rate(test_company, "USD", "2.70", date(2026, 8, 1))
    await _add_rate(test_company, "USD", "2.80", date(2026, 8, 2))  # stronger

    resp = await client.post("/api/v1/gl/exchange-differences/run", params={"on_date": "2026-08-02"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["revaluated"] == 1
    assert data["posted_entries"] == 1
    assert data["total_difference"] == 10.0  # 100 * (2.80 - 2.70)

    # Difference log persisted
    async with TestSessionLocal() as session:
        diff = (await session.execute(select(ExchangeDifference).where(
            ExchangeDifference.receivable_id == uuid.UUID(rec_id),
        ))).scalars().first()
        assert diff is not None
        assert diff.currency == "USD"
        assert diff.gel_equivalent == Decimal("280.00")
        assert diff.previous_gel_equivalent == Decimal("270.00")
        assert diff.difference == Decimal("10.00")

        # Journal entry: Dr AR, Cr income (5401) — balanced
        entry = (await session.execute(select(JournalEntry).where(
            JournalEntry.id == diff.journal_entry_id,
        ))).scalar_one()
        lines = (await session.execute(select(JournalEntryLine).where(
            JournalEntryLine.journal_entry_id == entry.id,
        ))).scalars().all()
        assert len(lines) == 2
        assert entry.reference_type == "exchange_difference"


async def test_revaluation_no_rate_skips(client: AsyncClient, auth_headers, test_company):
    await _seed_accounts(test_company)
    await _create_usd_receivable(client, auth_headers, test_company, Decimal("50.00"))
    # no rate at all
    resp = await client.post("/api/v1/gl/exchange-differences/run", params={"on_date": "2026-08-02"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["revaluated"] == 0
    assert data["posted_entries"] == 0


async def test_revaluation_first_run_no_difference(client: AsyncClient, auth_headers, test_company):
    await _seed_accounts(test_company)
    await _create_usd_receivable(client, auth_headers, test_company, Decimal("100.00"))
    await _add_rate(test_company, "USD", "2.70", date(2026, 8, 1))

    resp = await client.post("/api/v1/gl/exchange-differences/run", params={"on_date": "2026-08-01"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["revaluated"] == 1
    # First run establishes baseline → no journal entry
    assert resp.json()["data"]["posted_entries"] == 0


async def test_revaluation_loss_uses_expense_account(client: AsyncClient, auth_headers, test_company):
    await _seed_accounts(test_company)
    await _create_usd_receivable(client, auth_headers, test_company, Decimal("100.00"))
    await _add_rate(test_company, "USD", "2.80", date(2026, 8, 1))
    await _add_rate(test_company, "USD", "2.70", date(2026, 8, 2))  # weaker → loss

    resp = await client.post("/api/v1/gl/exchange-differences/run", params={"on_date": "2026-08-02"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total_difference"] == -10.0

"""Supplier Finance GL integrity: payment reversal, credit note and bank
reconciliation must post against AP (2100) — NOT goods-in-transit (2110).

Regression for the P0 accounting bug where reversal/credit-note used 2110
while the main payable is created on 2100, which would corrupt GL balances.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.gl import JournalEntry, JournalEntryLine
from app.services.gl_hooks import (
    post_supplier_payment_reversal_gl,
    post_supplier_credit_note_gl,
    post_supplier_bank_reconciliation_gl,
    post_supplier_bank_reconciliation_reversal_gl,
)

pytestmark = pytest.mark.asyncio


async def _account_codes(db, entry_id: uuid.UUID) -> set[str]:
    from app.models.gl import GLAccount
    rows = (
        await db.execute(
            select(GLAccount.code)
            .join(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
            .where(JournalEntryLine.journal_entry_id == entry_id)
        )
    ).scalars().all()
    return set(rows)


async def test_supplier_payment_reversal_uses_ap_2100(
    db_session, test_company, test_admin
):
    """Payment reversal must restore AP on 2100, never touch 2110."""
    await post_supplier_payment_reversal_gl(
        db_session,
        test_company.id,
        test_admin,
        reversal_id=uuid.uuid4(),
        payment_id=uuid.uuid4(),
        internal_invoice_number="SINV-TEST-001",
        reversal_date=date.today(),
        amount=Decimal("100.00"),
    )
    await db_session.commit()

    entries = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.company_id == test_company.id,
                JournalEntry.reference_type == "supplier_payment_reversal",
            )
        )
    ).scalars().all()
    assert len(entries) == 1
    codes = await _account_codes(db_session, entries[0].id)
    assert "2100" in codes, f"AP 2100 missing in reversal entry: {codes}"
    assert "2110" not in codes, f"goods-in-transit 2110 must NOT be used: {codes}"


async def test_supplier_credit_note_uses_ap_2100(
    db_session, test_company, test_admin
):
    """Credit note must reduce AP on 2100, never touch 2110."""
    await post_supplier_credit_note_gl(
        db_session,
        test_company.id,
        test_admin,
        credit_note_id=uuid.uuid4(),
        payable_id=uuid.uuid4(),
        internal_invoice_number="SINV-TEST-002",
        credit_date=date.today(),
        amount=Decimal("50.00"),
    )
    await db_session.commit()

    entries = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.company_id == test_company.id,
                JournalEntry.reference_type == "supplier_credit_note",
            )
        )
    ).scalars().all()
    assert len(entries) == 1
    codes = await _account_codes(db_session, entries[0].id)
    assert "2100" in codes, f"AP 2100 missing in credit note entry: {codes}"
    assert "2110" not in codes, f"goods-in-transit 2110 must NOT be used: {codes}"


async def test_supplier_bank_reconciliation_uses_ap_2100(
    db_session, test_company, test_admin
):
    """Bank reconciliation must reduce AP on 2100, never touch 2110."""
    await post_supplier_bank_reconciliation_gl(
        db_session,
        test_company.id,
        test_admin,
        reconciliation_id=uuid.uuid4(),
        payment_id=uuid.uuid4(),
        internal_invoice_number="SINV-TEST-003",
        reconciliation_date=date.today(),
        amount=Decimal("75.00"),
    )
    await db_session.commit()

    entries = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.company_id == test_company.id,
                JournalEntry.reference_type == "supplier_bank_reconciliation",
            )
        )
    ).scalars().all()
    assert len(entries) == 1
    codes = await _account_codes(db_session, entries[0].id)
    assert "2100" in codes, f"AP 2100 missing in reconciliation entry: {codes}"
    assert "2110" not in codes, f"goods-in-transit 2110 must NOT be used: {codes}"


async def test_supplier_bank_reconciliation_reversal_uses_ap_2100(
    db_session, test_company, test_admin
):
    """Reconciliation reversal must restore AP on 2100, never touch 2110."""
    await post_supplier_bank_reconciliation_reversal_gl(
        db_session,
        test_company.id,
        test_admin,
        reversal_id=uuid.uuid4(),
        reconciliation_id=uuid.uuid4(),
        internal_invoice_number="SINV-TEST-004",
        reversal_date=date.today(),
        amount=Decimal("30.00"),
    )
    await db_session.commit()

    entries = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.company_id == test_company.id,
                JournalEntry.reference_type == "supplier_bank_reconciliation_reversal",
            )
        )
    ).scalars().all()
    assert len(entries) == 1
    codes = await _account_codes(db_session, entries[0].id)
    assert "2100" in codes, f"AP 2100 missing in reversal entry: {codes}"
    assert "2110" not in codes, f"goods-in-transit 2110 must NOT be used: {codes}"


async def test_gl_entries_balanced_after_fixes(
    db_session, test_company, test_admin
):
    """All posted entries must stay balanced (debit == credit)."""
    await post_supplier_payment_reversal_gl(
        db_session, test_company.id, test_admin,
        reversal_id=uuid.uuid4(), payment_id=uuid.uuid4(),
        internal_invoice_number="SINV-TEST-005", reversal_date=date.today(),
        amount=Decimal("100.00"),
    )
    await post_supplier_credit_note_gl(
        db_session, test_company.id, test_admin,
        credit_note_id=uuid.uuid4(), payable_id=uuid.uuid4(),
        internal_invoice_number="SINV-TEST-006", credit_date=date.today(),
        amount=Decimal("40.00"),
    )
    await db_session.commit()

    entries = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.company_id == test_company.id,
                JournalEntry.reference_type.in_(["supplier_payment_reversal", "supplier_credit_note"]),
            )
        )
    ).scalars().all()
    assert len(entries) == 2
    for entry in entries:
        lines = (
            await db_session.execute(
                select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id)
            )
        ).scalars().all()
        debit = sum(Decimal(line.debit_amount) for line in lines)
        credit = sum(Decimal(line.credit_amount) for line in lines)
        assert debit == credit, f"Unbalanced GL entry {entry.entry_number}"

"""RS.ge VAT declaration submit — sandbox mode test (no credentials configured)."""
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _post_vat_entry(db, company, code: str, amount) -> None:
    acc = (await db.execute(select(GLAccount).where(GLAccount.company_id == company.id, GLAccount.code == code))).scalar_one()
    entry = JournalEntry(
        company_id=company.id, entry_date=date(2026, 8, 15),
        description="VAT test", reference_type="manual",
        reference_id=uuid.uuid4(), entry_number=f"VAT-TEST-{code}",
    )
    db.add(entry)
    await db.flush()
    if code.startswith("4"):
        db.add(JournalEntryLine(journal_entry_id=entry.id, gl_account_id=acc.id, line_number=1, debit_amount=0, credit_amount=amount))
    else:
        db.add(JournalEntryLine(journal_entry_id=entry.id, gl_account_id=acc.id, line_number=1, debit_amount=amount, credit_amount=0))
    await db.flush()


async def test_submit_vat_sandbox(client, auth_headers, test_company, db_session):
    # seed default accounts (4100 income, 5100 expense present in COA)
    from app.services.gl_posting import seed_default_accounts
    await seed_default_accounts(db_session, test_company.id)
    await db_session.commit()

    await _post_vat_entry(db_session, test_company, "4100", 1180)  # revenue incl VAT
    await _post_vat_entry(db_session, test_company, "5100", 590)   # purchases incl VAT
    await db_session.commit()

    resp = await client.post("/api/v1/srs/vat-declaration/submit", json={"year": 2026, "month": 8}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["mode"] == "sandbox"  # RS credentials not configured in tests
    assert data["period"] == "2026-08"
    # revenue 1180 → vat 180; expenses 590 → vat 90; net 90
    assert abs(data["vat_payable"] - 180.0) < 0.01
    assert abs(data["vat_credit"] - 90.0) < 0.01
    assert abs(data["net_vat"] - 90.0) < 0.01

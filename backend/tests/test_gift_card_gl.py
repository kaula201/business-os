"""Gift card GL integration — issue/redeem posts to the ledger."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_gift_card_gl(client, auth_headers, test_company, db_session):
    from app.services.gl_posting import seed_default_accounts
    await seed_default_accounts(db_session, test_company.id)
    await db_session.commit()

    # issue 100 GEL card → Dr 1410 100 / Cr 2800 100
    resp = await client.post("/api/v1/pos/gift-cards", params={"amount": 100}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    card_id = resp.json()["data"]["id"]

    async with TestSessionLocal() as s:
        entry = (await s.execute(select(JournalEntry).where(
            JournalEntry.reference_type == "gift_card_issue",
        ))).scalars().first()
        assert entry is not None
        lines = (await s.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))).scalars().all()
        codes = {}
        for l in lines:
            acct = (await s.execute(select(GLAccount).where(GLAccount.id == l.gl_account_id))).scalar_one()
            codes[acct.code] = (float(l.debit_amount), float(l.credit_amount))
        assert codes["1410"] == (100.0, 0.0)
        assert codes["2800"] == (0.0, 100.0)

    # redeem 40 → Dr 2800 40 / Cr 1410 40
    resp = await client.post(
        f"/api/v1/pos/gift-cards/{card_id}/redeem", params={"amount": 40}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text

    async with TestSessionLocal() as s:
        entry = (await s.execute(select(JournalEntry).where(
            JournalEntry.reference_type == "gift_card_redeem",
        ))).scalars().first()
        assert entry is not None
        lines = (await s.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))).scalars().all()
        codes = {}
        for l in lines:
            acct = (await s.execute(select(GLAccount).where(GLAccount.id == l.gl_account_id))).scalar_one()
            codes[acct.code] = (float(l.debit_amount), float(l.credit_amount))
        assert codes["2800"] == (40.0, 0.0)
        assert codes["1410"] == (0.0, 40.0)

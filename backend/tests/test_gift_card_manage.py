"""Gift card edit (status/expiry) and void with GL reversal."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.pos_extended import GiftCard
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_gift_card_edit_and_void(client, auth_headers, test_company, db_session):
    from app.services.gl_posting import seed_default_accounts
    await seed_default_accounts(db_session, test_company.id)
    await db_session.commit()

    resp = await client.post("/api/v1/pos/gift-cards", params={"amount": 100}, headers=auth_headers)
    card_id = resp.json()["data"]["id"]

    # block
    resp = await client.patch(f"/api/v1/pos/gift-cards/{card_id}", params={"status": "blocked"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "blocked"

    # unblock + new expiry
    resp = await client.patch(f"/api/v1/pos/gift-cards/{card_id}", params={"status": "active", "expires_at": "2027-01-01"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text

    async with TestSessionLocal() as s:
        card = (await s.execute(select(GiftCard).where(GiftCard.id == card_id))).scalar_one()
        assert card.status == "active"
        assert card.expires_at.isoformat() == "2027-01-01"

    # void → balance 0, status voided, GL reversal Dr 2800 / Cr 1410
    resp = await client.post(f"/api/v1/pos/gift-cards/{card_id}/void", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["refunded"] == 100.0

    async with TestSessionLocal() as s:
        card = (await s.execute(select(GiftCard).where(GiftCard.id == card_id))).scalar_one()
        assert card.status == "voided"
        assert card.balance == Decimal("0")

        entry = (await s.execute(select(JournalEntry).where(
            JournalEntry.reference_type == "gift_card_redeem",
            JournalEntry.reference_id == card_id,
        ))).scalars().first()
        assert entry is not None
        lines = (await s.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))).scalars().all()
        codes = {}
        for l in lines:
            acct = (await s.execute(select(GLAccount).where(GLAccount.id == l.gl_account_id))).scalar_one()
            codes[acct.code] = (float(l.debit_amount), float(l.credit_amount))
        assert codes["2800"] == (100.0, 0.0)
        assert codes["1410"] == (0.0, 100.0)

    # void again → 409
    resp = await client.post(f"/api/v1/pos/gift-cards/{card_id}/void", headers=auth_headers)
    assert resp.status_code == 409, resp.text

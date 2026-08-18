"""Consolidation elimination lifecycle: draft → balanced GL approval → reversal."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.company import Company
from app.models.consolidation_elimination import ConsolidationElimination
from app.models.gl import JournalEntry, JournalEntryLine
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_elimination_approval_and_reversal_are_balanced(client, auth_headers, test_company):
    group = uuid.uuid4()
    async with TestSessionLocal() as s:
        own = (await s.execute(select(Company).where(Company.id == test_company.id))).scalar_one()
        own.company_group_id = group
        other = Company(name="Elim Counterparty", identification_code="ELIM-002", currency="GEL", company_group_id=group)
        s.add(other)
        await s.commit()
        await s.refresh(other)

    draft = await client.post("/api/v1/gl/consolidation-eliminations/", json={
        "counterparty_company_id": str(other.id), "elimination_date": "2026-08-31",
        "revenue_account": "4100", "expense_account": "5200", "amount": 125,
        "idempotency_key": "elim-test-1",
    }, headers=auth_headers)
    assert draft.status_code == 201, draft.text
    elimination_id = draft.json()["data"]["id"]

    approved = await client.post(f"/api/v1/gl/consolidation-eliminations/{elimination_id}/approve", headers=auth_headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"

    async with TestSessionLocal() as s:
        entry = (await s.execute(select(JournalEntry).where(JournalEntry.reference_type == "consolidation_elimination"))).scalar_one()
        lines = (await s.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))).scalars().all()
        assert sum(x.debit_amount for x in lines) == sum(x.credit_amount for x in lines) == Decimal("125")

    reversed_ = await client.post(f"/api/v1/gl/consolidation-eliminations/{elimination_id}/reverse", headers=auth_headers)
    assert reversed_.status_code == 200, reversed_.text
    assert reversed_.json()["data"]["status"] == "reversed"

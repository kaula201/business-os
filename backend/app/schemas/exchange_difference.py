"""Exchange difference (revaluation) Pydantic schemas."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ExchangeDifferenceResponse(BaseModel):
    id: UUID
    company_id: UUID
    receivable_id: UUID | None
    payable_id: UUID | None
    cash_account_id: UUID | None
    bank_account_id: UUID | None
    currency: str
    revaluation_date: date
    outstanding_amount: float
    rate: float
    gel_equivalent: float
    previous_gel_equivalent: float | None
    difference: float
    journal_entry_id: UUID | None
    created_at: datetime


class ExchangeDifferenceRunResponse(BaseModel):
    revaluated: int
    posted_entries: int
    total_difference: float = 0

"""General Ledger Pydantic schemas."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class GLAccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=255)
    account_type: str = Field(min_length=1, max_length=20)
    parent_id: UUID | None = None
    description: str | None = None


class GLAccountUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    description: str | None = None


class GLAccountResponse(BaseModel):
    id: UUID
    company_id: UUID
    code: str
    name: str
    account_type: str
    parent_id: UUID | None
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class JournalEntryLineResponse(BaseModel):
    id: UUID
    journal_entry_id: UUID
    gl_account_id: UUID
    line_number: int
    debit_amount: float
    credit_amount: float
    description: str | None
    created_at: datetime


class JournalEntryResponse(BaseModel):
    id: UUID
    company_id: UUID
    entry_number: str
    entry_date: date
    description: str
    reference_type: str
    reference_id: UUID
    is_reversal: bool
    reversed_entry_id: UUID | None
    created_by: UUID | None
    created_at: datetime
    lines: list[JournalEntryLineResponse] = []


class JournalEntryListResponse(BaseModel):
    id: UUID
    entry_number: str
    entry_date: date
    description: str
    reference_type: str
    is_reversal: bool
    created_at: datetime


class JournalEntryLineCreate(BaseModel):
    gl_account_id: UUID
    debit_amount: float = 0
    credit_amount: float = 0
    description: str | None = None


class JournalEntryCreate(BaseModel):
    entry_date: date
    description: str = Field(min_length=1, max_length=1000)
    lines: list[JournalEntryLineCreate] = Field(min_length=2, max_length=200)

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Cash Account ─────────────────────────────────────────────────────

class CashAccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    currency: str = Field("GEL", min_length=3, max_length=3)
    opening_balance: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    responsible_person: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class CashAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None
    opening_balance: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    responsible_person: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class CashAccountResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    currency: str
    balance: float
    opening_balance: float
    responsible_person: str | None
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Cash Transaction ─────────────────────────────────────────────────

class CashTransactionCreate(BaseModel):
    cash_account_id: UUID
    transaction_date: date
    direction: str = Field(..., pattern="^(inflow|outflow)$")
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    category: str = Field(..., max_length=50)
    description: str = Field(default="", max_length=2000)
    counterparty: str | None = Field(default=None, max_length=255)
    receipt_number: str | None = Field(default=None, max_length=100)
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: UUID | None = None


class CashTransactionResponse(BaseModel):
    id: UUID
    company_id: UUID
    cash_account_id: UUID
    cash_account_name: str
    transaction_date: date
    direction: str
    amount: float
    category: str
    description: str
    counterparty: str | None
    receipt_number: str | None
    reference_type: str | None
    reference_id: UUID | None
    created_by: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Daily Report ─────────────────────────────────────────────────────

class CashDailyReport(BaseModel):
    date: date
    opening_balance: float
    total_inflow: float
    total_outflow: float
    closing_balance: float
    transaction_count: int

"""Recurring journal entry Pydantic schemas."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RecurringLine(BaseModel):
    gl_account_id: UUID
    debit_amount: float = 0
    credit_amount: float = 0
    description: str | None = None


class RecurringJournalEntryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    frequency: str = Field(pattern="^(daily|weekly|monthly)$")
    interval: int = Field(default=1, ge=1, le=365)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    start_date: date
    end_date: date | None = None
    entry_description: str = Field(min_length=1, max_length=1000)
    lines: list[RecurringLine] = Field(min_length=2, max_length=200)

    @field_validator("day_of_week")
    @classmethod
    def weekday_required_for_weekly(cls, v, info):
        if info.data.get("frequency") == "weekly" and v is None:
            raise ValueError("weekly-ისთვის day_of_week სავალდებულოა")
        return v

    @field_validator("day_of_month")
    @classmethod
    def day_required_for_monthly(cls, v, info):
        if info.data.get("frequency") == "monthly" and v is None:
            raise ValueError("monthly-ისთვის day_of_month სავალდებულოა")
        return v


class RecurringJournalEntryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    frequency: str | None = Field(default=None, pattern="^(daily|weekly|monthly)$")
    interval: int | None = Field(default=None, ge=1, le=365)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    end_date: date | None = None
    entry_description: str | None = None
    lines: list[RecurringLine] | None = None
    is_active: bool | None = None


class RecurringJournalEntryResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    description: str | None
    frequency: str
    interval: int
    day_of_week: int | None
    day_of_month: int | None
    start_date: date
    end_date: date | None
    next_run_date: date
    last_run_date: date | None
    lines: list
    entry_description: str
    is_active: bool
    total_posted: int
    created_at: datetime
    updated_at: datetime


class RecurringRunResponse(BaseModel):
    posted: int
    entry_numbers: list[str] = []

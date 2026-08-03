from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


CONTRACT_STATUSES = {"draft", "active", "expired", "terminated"}


class ContractCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    counterparty: str = Field(min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    value: Decimal = Field(default=Decimal("0"), ge=0)
    status: str = Field(default="draft", max_length=20)
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in CONTRACT_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(CONTRACT_STATUSES)}, got '{v}'"
            )
        return v


class ContractUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    counterparty: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    value: Decimal | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, max_length=20)
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in CONTRACT_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(CONTRACT_STATUSES)}, got '{v}'"
            )
        return v


class ContractResponse(BaseModel):
    id: UUID
    company_id: UUID
    title: str
    counterparty: str
    start_date: date | None
    end_date: date | None
    value: Decimal
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

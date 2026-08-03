from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

SUBSCRIPTION_FREQUENCIES = {"monthly", "yearly", "one_time"}
SUBSCRIPTION_STATUSES = {"active", "paused", "cancelled", "expired"}


class SubscriptionCreate(BaseModel):
    client_id: UUID
    plan: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    frequency: str = Field(default="monthly", max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    status: str = Field(default="active", max_length=20)

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        if v not in SUBSCRIPTION_FREQUENCIES:
            raise ValueError(
                f"frequency must be one of {sorted(SUBSCRIPTION_FREQUENCIES)}, got '{v}'"
            )
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in SUBSCRIPTION_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(SUBSCRIPTION_STATUSES)}, got '{v}'"
            )
        return v


class SubscriptionUpdate(BaseModel):
    client_id: UUID | None = None
    plan: str | None = Field(default=None, min_length=1, max_length=255)
    amount: Decimal | None = Field(default=None, ge=0)
    frequency: str | None = Field(default=None, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = Field(default=None, max_length=20)

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str | None) -> str | None:
        if v is not None and v not in SUBSCRIPTION_FREQUENCIES:
            raise ValueError(
                f"frequency must be one of {sorted(SUBSCRIPTION_FREQUENCIES)}, got '{v}'"
            )
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in SUBSCRIPTION_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(SUBSCRIPTION_STATUSES)}, got '{v}'"
            )
        return v


class SubscriptionResponse(BaseModel):
    id: UUID
    company_id: UUID
    client_id: UUID
    plan: str
    amount: Decimal
    frequency: str
    start_date: date | None
    end_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

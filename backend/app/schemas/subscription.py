from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

SUBSCRIPTION_FREQUENCIES = {"monthly", "yearly", "one_time"}
SUBSCRIPTION_STATUSES = {"active", "paused", "cancelled", "expired", "past_due"}


class SubscriptionPlanCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    frequency: str = Field(default="monthly", max_length=20)
    description: str | None = None


class SubscriptionPlanUpdate(BaseModel):
    name: str | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    frequency: str | None = None
    description: str | None = None
    is_active: bool | None = None


class SubscriptionPlanResponse(BaseModel):
    id: UUID
    company_id: UUID
    code: str
    name: str
    version: int
    amount: Decimal
    frequency: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionCreate(BaseModel):
    client_id: UUID
    plan: str = Field(min_length=1, max_length=255)
    plan_id: UUID | None = None
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    frequency: str = Field(default="monthly", max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    next_billing_date: date | None = None
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
    plan_id: UUID | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    frequency: str | None = Field(default=None, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    next_billing_date: date | None = None
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
    plan_id: UUID | None = None
    plan_version: int = 1
    amount: Decimal
    frequency: str
    start_date: date | None
    end_date: date | None
    next_billing_date: date | None
    status: str
    billing_attempts: int = 0
    max_billing_attempts: int = 3
    last_billing_error: str | None = None
    last_billed_at: datetime | None = None
    paused_at: datetime | None = None
    paused_reason: str | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionPauseRequest(BaseModel):
    reason: str | None = None


class SubscriptionResumeRequest(BaseModel):
    prorate: bool = True


class SubscriptionCancelRequest(BaseModel):
    reason: str | None = None


class SubscriptionChangePlanRequest(BaseModel):
    plan_id: UUID
    prorate: bool = True


class SubscriptionAnalyticsResponse(BaseModel):
    mrr: float
    arr: float
    active_subscriptions: int
    churned_subscriptions: int
    churn_rate: float
    new_subscriptions: int
    cohorts: list[dict]

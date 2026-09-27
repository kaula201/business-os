from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.saas import TENANT_FREQUENCIES, TENANT_STATUSES


class TenantPlanResponse(BaseModel):
    id: UUID
    code: str
    name: str
    amount: Decimal
    frequency: str
    feature_limits: dict
    description: str | None
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}


class TenantPlanCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    frequency: str = Field(default="monthly", max_length=20)
    feature_limits: dict = Field(default_factory=dict)
    description: str | None = None
    sort_order: int = 0

    @field_validator("frequency")
    @classmethod
    def _validate_frequency(cls, v: str) -> str:
        if v not in TENANT_FREQUENCIES:
            raise ValueError(f"frequency must be one of {sorted(TENANT_FREQUENCIES)}")
        return v


class TenantSubscriptionResponse(BaseModel):
    id: UUID
    company_id: UUID
    plan_id: UUID
    plan_code: str
    status: str
    frequency: str
    amount: Decimal
    feature_limits: dict
    start_date: date | None
    end_date: date | None
    trial_ends_at: date | None
    next_billing_date: date | None
    last_billed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantSubscribeRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=50)
    frequency: str = Field(default="monthly", max_length=20)
    trial_days: int = Field(default=14, ge=0, le=90)


class TenantEntitlementResponse(BaseModel):
    subscribed: bool
    plan_code: str | None
    status: str | None
    trial_ends_at: date | None
    feature_limits: dict
    # derived: is the tenant currently allowed to use the TMS module
    active: bool

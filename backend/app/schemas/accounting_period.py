from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AccountingPeriodAction(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


class AccountingPeriodResponse(BaseModel):
    id: UUID
    company_id: UUID
    year: int
    month: int
    start_date: date
    end_date: date
    status: str
    close_reason: str | None
    closed_by: UUID | None
    closed_at: datetime | None
    reopened_by: UUID | None
    reopened_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountingPeriodEventResponse(BaseModel):
    id: UUID
    period_id: UUID
    action: str
    reason: str
    actor_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

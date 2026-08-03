from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

LEAVE_STATUSES = {"pending", "approved", "rejected"}


class LeaveCreate(BaseModel):
    employee_id: UUID
    leave_type: str = Field(min_length=1, max_length=50)
    start_date: date
    end_date: date
    days: int | None = Field(default=None, ge=1)
    reason: str | None = None

    @field_validator("end_date")
    @classmethod
    def end_not_before_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


class LeaveUpdate(BaseModel):
    leave_type: str | None = Field(default=None, min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    days: int | None = Field(default=None, ge=1)
    reason: str | None = None


class LeaveApprove(BaseModel):
    """Approve or reject a leave request."""

    status: str = Field(...)
    reason: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in {"approved", "rejected"}:
            raise ValueError("status must be one of: approved, rejected")
        return v


class LeaveResponse(BaseModel):
    id: UUID
    company_id: UUID
    employee_id: UUID
    leave_type: str
    start_date: date
    end_date: date
    days: int
    status: str
    reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

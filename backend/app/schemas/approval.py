from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApprovalRequestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    approval_type: str = Field(..., min_length=1, max_length=50)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)


class ApprovalRequestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    approval_type: str | None = Field(default=None, min_length=1, max_length=50)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)


class ApprovalRequestResponse(BaseModel):
    id: UUID
    company_id: UUID
    title: str
    description: str | None
    approval_type: str
    amount: float | None
    status: str
    requested_by: UUID
    requested_by_name: str | None = None
    approved_by: UUID | None
    approved_by_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalApprove(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$", description="approve or reject")

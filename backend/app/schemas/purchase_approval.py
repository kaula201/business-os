from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PurchaseApprovalPolicyUpdate(BaseModel):
    manager_approval_limit: Decimal = Field(..., ge=0, max_digits=18, decimal_places=2)


class PurchaseApprovalPolicyResponse(BaseModel):
    manager_approval_limit: float
    updated_by: UUID | None = None
    updated_at: datetime | None = None

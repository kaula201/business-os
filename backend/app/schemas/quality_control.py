# backend/app/schemas/quality_control.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QualityCheckCreate(BaseModel):
    product_id: UUID
    checked_by: UUID
    status: str = Field(default="pending", description="pass, fail, or pending")
    notes: Optional[str] = None
    checked_at: Optional[datetime] = None


class QualityCheckUpdate(BaseModel):
    product_id: Optional[UUID] = None
    checked_by: Optional[UUID] = None
    status: Optional[str] = Field(None, description="pass, fail, or pending")
    notes: Optional[str] = None
    checked_at: Optional[datetime] = None


class QualityCheckResponse(BaseModel):
    id: UUID
    company_id: UUID
    product_id: UUID
    checked_by: UUID
    status: str
    notes: Optional[str] = None
    checked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

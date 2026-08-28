from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

EMAIL_CAMPAIGN_STATUSES = {"draft", "sent", "scheduled", "cancelled"}


class EmailCampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(default="", max_length=100000)
    audience: Any | None = None
    status: str = Field(default="draft", max_length=20)
    scheduled_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in EMAIL_CAMPAIGN_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(EMAIL_CAMPAIGN_STATUSES)}, got '{v}'"
            )
        return v


class EmailCampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    subject: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, max_length=100000)
    audience: Any | None = None
    status: str | None = Field(default=None, max_length=20)
    scheduled_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in EMAIL_CAMPAIGN_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(EMAIL_CAMPAIGN_STATUSES)}, got '{v}'"
            )
        return v


class EmailCampaignResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    subject: str
    body: str
    audience: Any | None
    status: str
    scheduled_at: datetime | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

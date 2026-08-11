"""Email tracking + e-signature schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Email tracking ───────────────────────────────────────────────────────────

class EmailEventCreate(BaseModel):
    campaign_id: UUID
    recipient_email: str = Field(min_length=3, max_length=255)
    event_type: str = Field(pattern="^(sent|opened|clicked)$")


class EmailEventResponse(BaseModel):
    id: UUID
    company_id: UUID
    campaign_id: UUID
    recipient_email: str
    event_type: str
    occurred_at: datetime


class CampaignStatsResponse(BaseModel):
    campaign_id: UUID
    sent: int = 0
    opened: int = 0
    clicked: int = 0
    open_rate: float = 0
    click_rate: float = 0


# ── E-signature ──────────────────────────────────────────────────────────────

class SignatureRequestCreate(BaseModel):
    document_name: str = Field(min_length=1, max_length=255)
    document_url: str | None = None
    signer_name: str = Field(min_length=1, max_length=255)
    signer_email: str = Field(min_length=3, max_length=255)
    message: str | None = None


class SignatureSignRequest(BaseModel):
    token: str = Field(min_length=8)
    signer_email: str = Field(min_length=3, max_length=255)
    decision: str = Field(pattern="^(sign|decline)$")


class SignatureRequestResponse(BaseModel):
    id: UUID
    company_id: UUID
    document_name: str
    document_url: str | None
    signer_name: str
    signer_email: str
    status: str
    signed_at: datetime | None
    signed_by_email: str | None
    message: str | None
    created_at: datetime
    updated_at: datetime

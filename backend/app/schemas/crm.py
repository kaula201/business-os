from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.schemas.client import ClientResponse


LeadSource = Literal["website", "referral", "campaign", "phone", "email", "other"]
LeadStatus = Literal["new", "contacted", "qualified", "unqualified", "converted"]
OpportunityStage = Literal["qualification", "discovery", "proposal", "negotiation", "won", "lost"]
ActivityType = Literal["call", "meeting", "email", "task", "note"]
ActivityStatus = Literal["planned", "completed", "cancelled"]


class CRMLeadCreate(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    contact_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    source: LeadSource = "other"
    estimated_value: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None
    owner_id: UUID | None = None
    next_action_date: date | None = None


class CRMLeadUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=2, max_length=255)
    contact_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    source: LeadSource | None = None
    status: LeadStatus | None = None
    estimated_value: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    owner_id: UUID | None = None
    next_action_date: date | None = None


class CRMLeadResponse(BaseModel):
    id: UUID
    company_id: UUID
    owner_id: UUID | None
    converted_client_id: UUID | None
    company_name: str
    contact_name: str | None
    email: str | None
    phone: str | None
    source: str
    status: str
    estimated_value: Decimal
    notes: str | None
    next_action_date: date | None
    last_activity_at: datetime | None
    converted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CRMLeadConvertRequest(BaseModel):
    client_type: Literal["legal", "individual"]
    identification_code: str = Field(min_length=2, max_length=50)
    is_vat_payer: bool = True
    name: str | None = Field(default=None, min_length=2, max_length=255)
    address: str | None = None
    notes: str | None = None


class CRMLeadConvertResponse(BaseModel):
    lead: CRMLeadResponse
    client: ClientResponse


class CRMOpportunityCreate(BaseModel):
    lead_id: UUID | None = None
    client_id: UUID | None = None
    name: str = Field(min_length=2, max_length=255)
    stage: OpportunityStage = "qualification"
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    probability: int = Field(default=10, ge=0, le=100)
    expected_close_date: date | None = None
    owner_id: UUID | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_related_party(self):
        if self.lead_id is None and self.client_id is None:
            raise ValueError("შესაძლებლობა ლიდს ან კლიენტს უნდა უკავშირდებოდეს")
        return self


class CRMOpportunityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    stage: OpportunityStage | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    lost_reason: str | None = None
    notes: str | None = None


class CRMOpportunityResponse(BaseModel):
    id: UUID
    company_id: UUID
    lead_id: UUID | None
    client_id: UUID | None
    owner_id: UUID | None
    name: str
    stage: str
    amount: Decimal
    probability: int
    expected_close_date: date | None
    lost_reason: str | None
    notes: str | None
    lead_company_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CRMActivityCreate(BaseModel):
    lead_id: UUID | None = None
    opportunity_id: UUID | None = None
    client_id: UUID | None = None
    assigned_to: UUID | None = None
    activity_type: ActivityType
    subject: str = Field(min_length=2, max_length=255)
    description: str | None = None
    due_at: datetime | None = None

    @model_validator(mode="after")
    def validate_relation(self):
        if sum(value is not None for value in (self.lead_id, self.opportunity_id, self.client_id)) != 1:
            raise ValueError("აქტივობა ზუსტად ერთ ლიდს, შესაძლებლობას ან კლიენტს უნდა უკავშირდებოდეს")
        return self


class CRMActivityUpdate(BaseModel):
    status: ActivityStatus | None = None
    subject: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    due_at: datetime | None = None
    assigned_to: UUID | None = None


class CRMActivityResponse(BaseModel):
    id: UUID
    company_id: UUID
    lead_id: UUID | None
    opportunity_id: UUID | None
    client_id: UUID | None
    assigned_to: UUID | None
    created_by: UUID
    activity_type: str
    subject: str
    description: str | None
    status: str
    due_at: datetime | None
    completed_at: datetime | None
    related_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Conversion Rate ──────────────────────────────────────────────────────────────

class ConversionRateResponse(BaseModel):
    total_leads: int
    converted_leads: int
    conversion_rate: float  # percentage
    period_days: int


# ── Pipeline Value by Stage ──────────────────────────────────────────────────────

class PipelineStageValue(BaseModel):
    stage: str
    stage_label: str
    count: int
    total_amount: Decimal
    weighted_amount: Decimal


class PipelineValueResponse(BaseModel):
    stages: list[PipelineStageValue]
    total_pipeline_value: Decimal
    total_weighted_value: Decimal


# ── Lead Source Tracking ──────────────────────────────────────────────────────────

class LeadSourceStats(BaseModel):
    source: str
    count: int
    total_value: Decimal
    converted_count: int
    conversion_rate: float  # percentage


class LeadSourceTrackingResponse(BaseModel):
    sources: list[LeadSourceStats]
    total_leads: int
    total_converted: int


# ── Stale Lead Alert ──────────────────────────────────────────────────────────────

class StaleLeadAlert(BaseModel):
    id: UUID
    company_name: str
    contact_name: str | None = None
    status: str
    source: str | None = None
    estimated_value: Decimal | None = None
    days_since_last_activity: int
    last_activity_at: datetime | None = None
    next_action_date: date | None = None
    owner_id: UUID | None = None
    created_at: datetime

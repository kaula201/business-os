"""Maintenance CMMS — Pydantic schemas."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Asset categories ────────────────────────────────────────────────────────

class MaintenanceAssetCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None


class MaintenanceAssetCategoryResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    description: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Locations ───────────────────────────────────────────────────────────────

class MaintenanceLocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    parent_id: UUID | None = None
    description: str | None = None


class MaintenanceLocationResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    parent_id: UUID | None
    description: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Assets ──────────────────────────────────────────────────────────────────

class MaintenanceAssetCreate(BaseModel):
    asset_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    category_id: UUID | None = None
    location_id: UUID | None = None
    parent_asset_id: UUID | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    status: str = "operational"
    install_date: date | None = None
    warranty_until: date | None = None
    purchase_cost: Decimal = Field(default=Decimal("0"), ge=0)
    expected_lifetime_years: int | None = Field(default=None, ge=0)
    qr_code: str | None = None
    notes: str | None = None


class MaintenanceAssetUpdate(BaseModel):
    name: str | None = None
    category_id: UUID | None = None
    location_id: UUID | None = None
    parent_asset_id: UUID | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    status: str | None = None
    install_date: date | None = None
    warranty_until: date | None = None
    purchase_cost: Decimal | None = Field(default=None, ge=0)
    expected_lifetime_years: int | None = Field(default=None, ge=0)
    qr_code: str | None = None
    notes: str | None = None


class MaintenanceAssetResponse(BaseModel):
    id: UUID
    company_id: UUID
    asset_code: str
    name: str
    category_id: UUID | None
    location_id: UUID | None
    parent_asset_id: UUID | None
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    status: str
    install_date: date | None
    warranty_until: date | None
    purchase_cost: Decimal
    expected_lifetime_years: int | None
    qr_code: str | None
    notes: str | None
    category_name: str | None = None
    location_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Meters ─────────────────────────────────────────────────────────────────

class MaintenanceMeterCreate(BaseModel):
    asset_id: UUID
    name: str = Field(min_length=1, max_length=100)
    unit: str = "hours"
    current_value: Decimal = Field(default=Decimal("0"), ge=0)


class MaintenanceMeterUpdate(BaseModel):
    current_value: Decimal | None = Field(default=None, ge=0)
    name: str | None = None
    unit: str | None = None


class MaintenanceMeterResponse(BaseModel):
    id: UUID
    company_id: UUID
    asset_id: UUID
    name: str
    unit: str
    current_value: Decimal
    last_reading_at: datetime | None
    asset_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Requests ───────────────────────────────────────────────────────────────

class MaintenanceRequestCreate(BaseModel):
    asset_id: UUID | None = None
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    priority: str = "medium"
    requested_by: UUID | None = None
    assigned_to: UUID | None = None
    requested_date: date | None = None


class MaintenanceRequestUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    assigned_to: UUID | None = None


class MaintenanceRequestResponse(BaseModel):
    id: UUID
    company_id: UUID
    request_number: str
    asset_id: UUID | None
    title: str
    description: str | None
    priority: str
    status: str
    requested_by: UUID | None
    assigned_to: UUID | None
    order_id: UUID | None
    requested_date: date
    completed_at: datetime | None
    asset_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Plans ──────────────────────────────────────────────────────────────────

class MaintenancePlanCreate(BaseModel):
    asset_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    plan_type: str = "preventive"
    interval_days: int = Field(default=30, ge=1)
    next_due_at: date | None = None
    assigned_to: UUID | None = None
    notes: str | None = None


class MaintenancePlanUpdate(BaseModel):
    name: str | None = None
    plan_type: str | None = None
    interval_days: int | None = Field(default=None, ge=1)
    next_due_at: date | None = None
    assigned_to: UUID | None = None
    is_active: bool | None = None
    notes: str | None = None


class MaintenancePlanResponse(BaseModel):
    id: UUID
    company_id: UUID
    asset_id: UUID | None
    name: str
    plan_type: str
    interval_days: int
    last_run_at: date | None
    next_due_at: date | None
    assigned_to: UUID | None
    is_active: bool
    notes: str | None
    asset_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Orders ─────────────────────────────────────────────────────────────────

class MaintenanceOrderCreate(BaseModel):
    plan_id: UUID | None = None
    request_id: UUID | None = None
    asset_id: UUID | None = None
    asset_name: str | None = None
    maintenance_type: str = "preventive"
    priority: str = "medium"
    scheduled_date: date | None = None
    assigned_to: UUID | None = None
    technician_id: UUID | None = None
    team_id: UUID | None = None
    is_emergency: bool = False
    failure_code: str | None = None
    failure_cause: str | None = None
    cost_estimate: Decimal = Field(default=Decimal("0"), ge=0)
    description: str | None = None


class MaintenanceOrderUpdate(BaseModel):
    maintenance_type: str | None = None
    priority: str | None = None
    status: str | None = None
    scheduled_date: date | None = None
    assigned_to: UUID | None = None
    technician_id: UUID | None = None
    team_id: UUID | None = None
    is_emergency: bool | None = None
    failure_code: str | None = None
    failure_cause: str | None = None
    cost_estimate: Decimal | None = Field(default=None, ge=0)
    actual_cost: Decimal | None = Field(default=None, ge=0)
    parts_cost: Decimal | None = Field(default=None, ge=0)
    labor_hours: Decimal | None = Field(default=None, ge=0)
    downtime_hours: Decimal | None = Field(default=None, ge=0)
    description: str | None = None
    resolution_notes: str | None = None


class MaintenanceOrderResponse(BaseModel):
    id: UUID
    company_id: UUID
    plan_id: UUID | None
    request_id: UUID | None
    order_number: str
    asset_id: UUID | None
    asset_name: str | None
    maintenance_type: str
    priority: str
    status: str
    scheduled_date: date | None
    started_at: datetime | None
    completed_at: datetime | None
    assigned_to: UUID | None
    technician_id: UUID | None
    team_id: UUID | None
    is_emergency: bool
    failure_code: str | None
    failure_cause: str | None
    cost_estimate: Decimal
    actual_cost: Decimal
    parts_cost: Decimal
    labor_hours: Decimal
    downtime_hours: Decimal
    description: str | None
    resolution_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Phase 2: Resources ──────────────────────────────────────────────────────

class MaintenanceTechnicianCreate(BaseModel):
    user_id: UUID | None = None
    name: str = Field(min_length=1, max_length=150)
    email: str | None = None
    phone: str | None = None
    specialization: str | None = None
    hourly_rate: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None


class MaintenanceTechnicianUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    specialization: str | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None
    notes: str | None = None


class MaintenanceTechnicianResponse(BaseModel):
    id: UUID
    company_id: UUID
    user_id: UUID | None
    name: str
    email: str | None
    phone: str | None
    specialization: str | None
    hourly_rate: Decimal
    is_active: bool
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenanceTeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    leader_id: UUID | None = None
    description: str | None = None


class MaintenanceTeamUpdate(BaseModel):
    name: str | None = None
    leader_id: UUID | None = None
    description: str | None = None
    is_active: bool | None = None


class MaintenanceTeamResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    leader_id: UUID | None
    description: str | None
    is_active: bool
    member_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenanceContractorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    specialization: str | None = None
    hourly_rate: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None


class MaintenanceContractorUpdate(BaseModel):
    name: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    specialization: str | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None
    notes: str | None = None


class MaintenanceContractorResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    contact_person: str | None
    email: str | None
    phone: str | None
    specialization: str | None
    hourly_rate: Decimal
    is_active: bool
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenanceSLACreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    priority: str = "medium"
    response_hours: Decimal = Field(default=Decimal("4"), ge=0)
    resolution_hours: Decimal = Field(default=Decimal("24"), ge=0)
    contractor_id: UUID | None = None


class MaintenanceSLAUpdate(BaseModel):
    name: str | None = None
    priority: str | None = None
    response_hours: Decimal | None = Field(default=None, ge=0)
    resolution_hours: Decimal | None = Field(default=None, ge=0)
    contractor_id: UUID | None = None
    is_active: bool | None = None


class MaintenanceSLAResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    priority: str
    response_hours: Decimal
    resolution_hours: Decimal
    contractor_id: UUID | None
    contractor_name: str | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenanceCertificateCreate(BaseModel):
    technician_id: UUID
    name: str = Field(min_length=1, max_length=150)
    issued_date: date | None = None
    expiry_date: date | None = None
    notes: str | None = None


class MaintenanceCertificateResponse(BaseModel):
    id: UUID
    company_id: UUID
    technician_id: UUID
    name: str
    issued_date: date | None
    expiry_date: date | None
    notes: str | None
    technician_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Phase 3: Parts & Tools ──────────────────────────────────────────────────

class MaintenancePartCreate(BaseModel):
    part_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    category: str | None = None
    unit: str = "ცალი"
    quantity_on_hand: Decimal = Field(default=Decimal("0"), ge=0)
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)
    location: str | None = None
    supplier: str | None = None
    notes: str | None = None


class MaintenancePartUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    quantity_on_hand: Decimal | None = Field(default=None, ge=0)
    reorder_level: Decimal | None = Field(default=None, ge=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    location: str | None = None
    supplier: str | None = None
    notes: str | None = None


class MaintenancePartResponse(BaseModel):
    id: UUID
    company_id: UUID
    part_code: str
    name: str
    category: str | None
    unit: str
    quantity_on_hand: Decimal
    reorder_level: Decimal
    unit_cost: Decimal
    location: str | None
    supplier: str | None
    notes: str | None
    is_low: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenancePartRequestCreate(BaseModel):
    part_id: UUID
    order_id: UUID | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0)


class MaintenancePartRequestUpdate(BaseModel):
    status: str | None = None


class MaintenancePartRequestResponse(BaseModel):
    id: UUID
    company_id: UUID
    part_id: UUID
    order_id: UUID | None
    quantity: Decimal
    status: str
    requested_by: UUID | None
    requested_at: datetime
    issued_at: datetime | None
    part_name: str | None = None
    part_code: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenanceToolCreate(BaseModel):
    tool_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    category: str | None = None
    quantity: int = Field(default=1, ge=1)
    notes: str | None = None


class MaintenanceToolUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    quantity: int | None = Field(default=None, ge=1)
    status: str | None = None
    notes: str | None = None


class MaintenanceToolResponse(BaseModel):
    id: UUID
    company_id: UUID
    tool_code: str
    name: str
    category: str | None
    quantity: int
    available: int
    status: str
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenanceToolIssueCreate(BaseModel):
    tool_id: UUID
    technician_id: UUID
    notes: str | None = None


class MaintenanceToolIssueResponse(BaseModel):
    id: UUID
    company_id: UUID
    tool_id: UUID
    technician_id: UUID
    issued_at: datetime
    returned_at: datetime | None
    notes: str | None
    tool_name: str | None = None
    technician_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

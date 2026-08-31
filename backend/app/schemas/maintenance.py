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

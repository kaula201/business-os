from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Vehicle ──────────────────────────────────────────────────────────

class VehicleCreate(BaseModel):
    plate_number: str = Field(..., min_length=1, max_length=20)
    brand: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    year: int | None = None
    vin: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    fuel_type: str = Field(default="petrol", max_length=20)
    engine_capacity: float | None = None
    tank_capacity_liters: float | None = Field(default=None, gt=0)
    initial_mileage: float = Field(default=0, ge=0)
    current_mileage: float = Field(default=0, ge=0)
    service_interval_km: float | None = Field(default=None, gt=0)
    service_interval_days: int | None = Field(default=None, gt=0)
    insurance_company: str | None = Field(default=None, max_length=255)
    insurance_policy: str | None = Field(default=None, max_length=100)
    insurance_valid_until: date | None = None
    tech_inspection_until: date | None = None
    location_name: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude და longitude ერთად უნდა იყოს მითითებული")
        return self


class VehicleUpdate(BaseModel):
    plate_number: str | None = Field(default=None, min_length=1, max_length=20)
    brand: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=100)
    year: int | None = None
    vin: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    fuel_type: str | None = Field(default=None, max_length=20)
    engine_capacity: float | None = None
    tank_capacity_liters: float | None = Field(default=None, gt=0)
    current_mileage: float | None = Field(default=None, ge=0)
    service_interval_km: float | None = Field(default=None, gt=0)
    service_interval_days: int | None = Field(default=None, gt=0)
    insurance_company: str | None = Field(default=None, max_length=255)
    insurance_policy: str | None = Field(default=None, max_length=100)
    insurance_valid_until: date | None = None
    tech_inspection_until: date | None = None
    location_name: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_active: bool | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        provided = self.model_fields_set
        if ("latitude" in provided) != ("longitude" in provided):
            raise ValueError("latitude და longitude ერთად უნდა იყოს მითითებული")
        if "latitude" in provided and (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude და longitude ერთად უნდა იყოს მითითებული")
        return self


class VehicleResponse(BaseModel):
    id: UUID
    company_id: UUID
    plate_number: str
    brand: str
    model: str
    year: int | None
    vin: str | None
    color: str | None
    fuel_type: str
    engine_capacity: float | None
    tank_capacity_liters: float | None
    initial_mileage: float
    current_mileage: float
    service_interval_km: float | None
    service_interval_days: int | None
    insurance_company: str | None
    insurance_policy: str | None
    insurance_valid_until: date | None
    tech_inspection_until: date | None
    location_name: str | None
    latitude: float | None
    longitude: float | None
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Fuel Log ─────────────────────────────────────────────────────────

class FuelLogCreate(BaseModel):
    vehicle_id: UUID
    refuel_date: date
    liters: float = Field(..., gt=0)
    price_per_liter: float = Field(..., gt=0)
    total_amount: float = Field(..., gt=0)
    mileage_at_refuel: float = Field(..., ge=0)
    fuel_card: str | None = Field(default=None, max_length=100)
    station: str | None = Field(default=None, max_length=255)
    receipt_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class FuelLogResponse(BaseModel):
    id: UUID
    company_id: UUID
    vehicle_id: UUID
    refuel_date: date
    liters: float
    price_per_liter: float
    total_amount: float
    mileage_at_refuel: float
    fuel_card: str | None
    station: str | None
    receipt_number: str | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Service Record ──────────────────────────────────────────────────

class ServiceRecordCreate(BaseModel):
    vehicle_id: UUID
    service_date: date
    service_type: str = Field(..., max_length=50)
    description: str = Field(..., min_length=1)
    mileage_at_service: float = Field(..., ge=0)
    cost: float = Field(default=0, ge=0)
    service_provider: str | None = Field(default=None, max_length=255)
    invoice_number: str | None = Field(default=None, max_length=100)
    next_service_mileage: float | None = Field(default=None, ge=0)
    next_service_date: date | None = None
    notes: str | None = None


class ServiceRecordResponse(BaseModel):
    id: UUID
    company_id: UUID
    vehicle_id: UUID
    service_date: date
    service_type: str
    description: str
    mileage_at_service: float
    cost: float
    service_provider: str | None
    invoice_number: str | None
    next_service_mileage: float | None
    next_service_date: date | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Driver Assignment ───────────────────────────────────────────────

class DriverAssignmentCreate(BaseModel):
    vehicle_id: UUID
    driver_name: str = Field(..., min_length=1, max_length=255)
    driver_phone: str | None = Field(default=None, max_length=50)
    driver_license: str | None = Field(default=None, max_length=50)
    assigned_from: date
    assigned_until: date | None = None
    notes: str | None = None


class DriverAssignmentUpdate(BaseModel):
    driver_name: str | None = Field(default=None, min_length=1, max_length=255)
    driver_phone: str | None = Field(default=None, max_length=50)
    driver_license: str | None = Field(default=None, max_length=50)
    assigned_from: date | None = None
    assigned_until: date | None = None
    is_active: bool | None = None
    notes: str | None = None


class DriverAssignmentResponse(BaseModel):
    id: UUID
    company_id: UUID
    vehicle_id: UUID
    driver_name: str
    driver_phone: str | None
    driver_license: str | None
    assigned_from: date
    assigned_until: date | None
    is_active: bool
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Odometer Reading ─────────────────────────────────────────────────

class OdometerReadingCreate(BaseModel):
    reading_date: date
    mileage_km: float = Field(..., ge=0)
    source: str | None = Field(default="manual", max_length=30)
    notes: str | None = None


class OdometerReadingResponse(BaseModel):
    id: UUID
    company_id: UUID
    vehicle_id: UUID
    reading_date: date
    mileage_km: float
    source: str | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

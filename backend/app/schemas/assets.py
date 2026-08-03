from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Fixed Asset ──────────────────────────────────────────────────────

class FixedAssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    asset_type: str = Field(..., max_length=50)
    purchase_date: date
    purchase_cost: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    useful_life_years: int = Field(..., ge=1)
    depreciation_method: str = Field("straight_line", max_length=20)
    salvage_value: Decimal = Field(Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    serial_number: str | None = Field(default=None, max_length=100)
    inventory_number: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    custodian: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    gl_account_id: UUID | None = None


class FixedAssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=255)
    custodian: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    serial_number: str | None = Field(default=None, max_length=100)
    inventory_number: str | None = Field(default=None, max_length=100)
    impairment_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    impairment_date: date | None = None
    disposal_date: date | None = None
    disposal_proceeds: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)


class FixedAssetResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    asset_type: str
    purchase_date: date
    purchase_cost: float
    useful_life_years: int
    depreciation_method: str
    salvage_value: float
    accumulated_depreciation: float
    book_value: float
    last_depreciation_date: date | None
    status: str
    serial_number: str | None
    inventory_number: str | None
    location: str | None
    custodian: str | None
    impairment_amount: float
    impairment_date: date | None
    disposal_date: date | None
    disposal_proceeds: float | None
    notes: str | None
    gl_account_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Depreciation ─────────────────────────────────────────────────────

class DepreciationRunResponse(BaseModel):
    asset_id: UUID
    asset_name: str
    depreciation_amount: float
    new_book_value: float
    new_accumulated_depreciation: float
    is_fully_depreciated: bool


class AssetDepreciationResponse(BaseModel):
    id: UUID
    asset_id: UUID
    depreciation_date: date
    amount: float
    period_label: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

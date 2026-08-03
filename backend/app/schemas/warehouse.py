from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Warehouse ──────────────────────────────────────────────────────────────────

class WarehouseCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    address: str | None = None
    is_default: bool = False


class WarehouseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = None


class WarehouseResponse(BaseModel):
    id: UUID
    code: str
    name: str
    address: str | None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Warehouse Zone / Location ──────────────────────────────────────────────────

class WarehouseZoneCreate(BaseModel):
    warehouse_id: UUID
    parent_id: UUID | None = None
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    zone_type: Literal["aisle", "rack", "shelf", "bin", "dock", "staging"] = "bin"
    is_pickable: bool = True
    sort_order: int = 0


class WarehouseZoneUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    zone_type: Literal["aisle", "rack", "shelf", "bin", "dock", "staging"] | None = None
    is_pickable: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    parent_id: UUID | None = None


class WarehouseZoneResponse(BaseModel):
    id: UUID
    warehouse_id: UUID
    parent_id: UUID | None
    code: str
    name: str
    zone_type: str
    is_pickable: bool
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ZoneBalanceResponse(BaseModel):
    id: UUID
    zone_id: UUID
    zone_code: str
    zone_name: str
    product_id: UUID
    product_name: str
    quantity: float
    updated_at: datetime


# ── Inventory Balance (with reserved/available/on-hand) ────────────────────────

class InventoryBalanceResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    warehouse_id: UUID
    warehouse_name: str
    warehouse_code: str
    quantity: float
    reserved_quantity: float
    available_quantity: float
    updated_at: datetime


# ── Stock Adjustment ───────────────────────────────────────────────────────────

class WarehouseStockAdjustment(BaseModel):
    product_id: UUID
    warehouse_id: UUID
    zone_id: UUID | None = None
    movement_type: Literal["in", "out", "adjustment"]
    quantity: float = Field(..., ge=0)
    reason: str = Field(..., min_length=1, max_length=100)
    reason_category: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def quantity_must_be_positive_for_movements(self):
        if self.movement_type != "adjustment" and self.quantity <= 0:
            raise ValueError("რაოდენობა ნულზე მეტი უნდა იყოს")
        return self


# ── Stock Transfer ─────────────────────────────────────────────────────────────

class StockTransferCreate(BaseModel):
    product_id: UUID
    source_warehouse_id: UUID
    destination_warehouse_id: UUID
    quantity: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=100)
    reason_category: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def warehouses_must_be_different(self):
        if self.source_warehouse_id == self.destination_warehouse_id:
            raise ValueError("საწყობები განსხვავებული უნდა იყოს")
        return self


class StockTransferResponse(BaseModel):
    reference: str
    product_id: UUID
    source_warehouse_id: UUID
    destination_warehouse_id: UUID
    quantity: float
    source_balance_after: float
    destination_balance_after: float


# ── Inventory Movement History ──────────────────────────────────────────────────

class InventoryMovementResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str | None = None
    warehouse_id: UUID
    warehouse_name: str | None = None
    zone_id: UUID | None = None
    zone_name: str | None = None
    movement_type: str
    quantity: float
    balance_before: float | None
    balance_after: float
    reserved_before: float | None
    reserved_after: float | None
    reason: str
    reason_category: str | None
    notes: str | None
    reference: str | None
    reference_type: str | None
    created_by: UUID | None
    created_at: datetime


# ── Inventory Count ────────────────────────────────────────────────────────────

class InventoryCountCreate(BaseModel):
    warehouse_id: UUID
    zone_id: UUID | None = None
    count_type: Literal["full", "spot", "cycle", "annual"] = "full"
    notes: str | None = None


class InventoryCountUpdate(BaseModel):
    status: Literal["draft", "in_progress", "completed", "cancelled", "posted"] | None = None
    notes: str | None = None


class InventoryCountResponse(BaseModel):
    id: UUID
    warehouse_id: UUID
    warehouse_name: str | None = None
    zone_id: UUID | None
    zone_name: str | None = None
    count_number: str
    status: str
    count_type: str
    notes: str | None
    counted_by: UUID | None
    approved_by: UUID | None
    counted_at: datetime | None
    approved_at: datetime | None
    line_count: int | None = None
    total_difference: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryCountLineCreate(BaseModel):
    product_id: UUID
    zone_id: UUID | None = None
    counted_quantity: float = Field(..., ge=0)
    notes: str | None = None


class InventoryCountLineUpdate(BaseModel):
    counted_quantity: float | None = Field(default=None, ge=0)
    notes: str | None = None


class InventoryCountLineResponse(BaseModel):
    id: UUID
    count_id: UUID
    product_id: UUID
    product_name: str | None = None
    zone_id: UUID | None
    zone_name: str | None = None
    expected_quantity: float
    counted_quantity: float | None
    difference: float | None
    notes: str | None
    created_at: datetime


# ── Count Post (apply count differences as adjustments) ─────────────────────────

class InventoryCountPostResult(BaseModel):
    count_id: UUID
    count_number: str
    lines_posted: int
    adjustments_created: int
    total_difference: float

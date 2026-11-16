"""Pydantic schemas for Production / Manufacturing module."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── BOM ────────────────────────────────────────────────────────────────────────

class BOMBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    product_id: UUID
    quantity: Decimal = Field(default=Decimal("1"), max_digits=14, decimal_places=3)
    labor_cost: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    overhead_cost: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    notes: Optional[str] = None


class BOMCreate(BOMBase):
    pass


class BOMResponse(BOMBase):
    id: UUID
    company_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class BOMDetailResponse(BOMResponse):
    """BOM with items and cost breakdown."""
    items: list["BOMItemResponse"] = []
    total_material_cost: Decimal = Decimal("0")
    total_labor_cost: Decimal = Decimal("0")
    total_overhead_cost: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")
    unit_cost: Decimal = Decimal("0")


# ── BOM Items ──────────────────────────────────────────────────────────────────

class BOMItemBase(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(default=Decimal("1"), max_digits=14, decimal_places=3)
    unit_cost: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    scrap_percent: Decimal = Field(default=Decimal("0"), max_digits=5, decimal_places=2)


class BOMItemCreate(BOMItemBase):
    pass


class BOMItemResponse(BOMItemBase):
    id: UUID
    bom_id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Work Centers ───────────────────────────────────────────────────────────────

class WorkCenterBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    work_center_type: str = Field(default="machine", max_length=30)
    hourly_rate: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    capacity_per_shift: Decimal = Field(default=Decimal("1"), max_digits=14, decimal_places=3)
    notes: Optional[str] = None


class WorkCenterCreate(WorkCenterBase):
    pass


class WorkCenterResponse(WorkCenterBase):
    id: UUID
    company_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Work Orders ─────────────────────────────────────────────────────────────────

class WorkOrderBase(BaseModel):
    bom_id: UUID
    product_id: UUID
    work_center_id: Optional[UUID] = None
    planned_quantity: Decimal = Field(default=Decimal("1"), max_digits=14, decimal_places=3)
    yield_percent: Decimal = Field(default=Decimal("100"), max_digits=5, decimal_places=2)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    assigned_to: Optional[UUID] = None
    notes: Optional[str] = None


class WorkOrderCreate(WorkOrderBase):
    pass


class WorkOrderUpdate(BaseModel):
    status: Optional[str] = None
    completed_quantity: Optional[Decimal] = None
    scrapped_quantity: Optional[Decimal] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    assigned_to: Optional[UUID] = None
    notes: Optional[str] = None


class WorkOrderResponse(WorkOrderBase):
    id: UUID
    company_id: UUID
    order_number: str
    completed_quantity: Decimal
    scrapped_quantity: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Production Reservations ────────────────────────────────────────────────────

class ProductionReservationBase(BaseModel):
    work_order_id: UUID
    product_id: UUID
    warehouse_id: UUID
    quantity_reserved: Decimal = Field(..., max_digits=18, decimal_places=3)


class ProductionReservationCreate(ProductionReservationBase):
    pass


class ProductionReservationResponse(ProductionReservationBase):
    id: UUID
    company_id: UUID
    quantity_consumed: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Component Availability ─────────────────────────────────────────────────────

class ComponentAvailabilityItem(BaseModel):
    product_id: UUID
    product_name: str
    product_sku: str
    required_quantity: Decimal
    available_quantity: Decimal
    short_quantity: Decimal
    is_available: bool


class ComponentAvailabilityResponse(BaseModel):
    work_order_id: UUID
    items: list[ComponentAvailabilityItem] = []
    all_available: bool


# ── Finished Goods Receipt ──────────────────────────────────────────────────────

class FinishedGoodsReceiptBase(BaseModel):
    work_order_id: UUID
    product_id: UUID
    warehouse_id: UUID
    quantity: Decimal = Field(..., max_digits=18, decimal_places=3)
    unit_cost: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    notes: Optional[str] = None


class FinishedGoodsReceiptCreate(FinishedGoodsReceiptBase):
    pass


class FinishedGoodsReceiptResponse(FinishedGoodsReceiptBase):
    id: UUID
    company_id: UUID
    receipt_number: str
    created_by: Optional[UUID]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── BOM Cost Calculation ───────────────────────────────────────────────────────

class BOMCostBreakdown(BaseModel):
    bom_id: UUID
    bom_code: str
    bom_name: str
    product_id: UUID
    bom_quantity: Decimal
    items: list["BOMItemResponse"] = []
    total_material_cost: Decimal
    total_labor_cost: Decimal
    total_overhead_cost: Decimal
    total_cost: Decimal
    unit_cost: Decimal


# ── Production 2.0: routing / operations / capacity / consumption / scrap / genealogy / MRP / downtime ──

class RoutingBase(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    product_id: UUID
    is_active: bool = True
    notes: Optional[str] = None


class RoutingCreate(RoutingBase):
    pass


class RoutingOperationCreate(BaseModel):
    work_center_id: Optional[UUID] = None
    sequence: int = 1
    name: str = Field(min_length=1, max_length=255)
    standard_time_minutes: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    setup_minutes: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    hourly_rate: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)


class RoutingOperationResponse(RoutingOperationCreate):
    id: UUID
    company_id: UUID
    routing_id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}


class RoutingResponse(RoutingBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    operations: list[RoutingOperationResponse] = []
    model_config = {"from_attributes": True}


class WorkOrderOperationStart(BaseModel):
    work_center_id: Optional[UUID] = None
    notes: Optional[str] = None


class WorkOrderOperationComplete(BaseModel):
    actual_minutes: Decimal = Field(..., max_digits=10, decimal_places=2)
    notes: Optional[str] = None


class WorkOrderOperationResponse(BaseModel):
    id: UUID
    company_id: UUID
    work_order_id: UUID
    sequence: int
    name: str
    work_center_id: Optional[UUID]
    standard_minutes: Decimal
    actual_minutes: Decimal
    actual_labor_cost: Decimal
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class WorkOrderConsumptionCreate(BaseModel):
    product_id: UUID
    warehouse_id: UUID
    quantity: Decimal = Field(..., gt=0, max_digits=18, decimal_places=3)
    unit_cost: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    notes: Optional[str] = None


class WorkOrderConsumptionResponse(BaseModel):
    id: UUID
    company_id: UUID
    work_order_id: UUID
    product_id: UUID
    warehouse_id: UUID
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    is_backflush: bool
    consumed_at: datetime
    created_at: datetime
    model_config = {"from_attributes": True}


class WorkOrderWipResponse(BaseModel):
    id: UUID
    company_id: UUID
    work_order_id: UUID
    material_cost: Decimal
    labor_cost: Decimal
    overhead_cost: Decimal
    total_cost: Decimal
    estimated_cost: Decimal
    variance: Decimal
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class WorkOrderScrapCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(..., gt=0, max_digits=18, decimal_places=3)
    kind: str = "scrap"  # scrap | by_product
    unit_cost: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    notes: Optional[str] = None


class WorkOrderScrapResponse(BaseModel):
    id: UUID
    company_id: UUID
    work_order_id: UUID
    product_id: UUID
    quantity: Decimal
    kind: str
    unit_cost: Decimal
    total_value: Decimal
    notes: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class GenealogyCreate(BaseModel):
    finished_lot: Optional[str] = None
    finished_serial: Optional[str] = None
    component_product_id: UUID
    component_lot: Optional[str] = None
    component_serial: Optional[str] = None
    quantity: Decimal = Field(default=Decimal("1"), max_digits=18, decimal_places=3)


class GenealogyResponse(BaseModel):
    id: UUID
    company_id: UUID
    work_order_id: UUID
    finished_product_id: UUID
    finished_lot: Optional[str]
    finished_serial: Optional[str]
    component_product_id: UUID
    component_lot: Optional[str]
    component_serial: Optional[str]
    quantity: Decimal
    created_at: datetime
    model_config = {"from_attributes": True}


class MrpRunResponse(BaseModel):
    generated: int
    make_suggestions: int
    buy_suggestions: int
    suggestions: list[dict] = []


class DowntimeWindowCreate(BaseModel):
    work_center_id: UUID
    start_time: datetime
    end_time: datetime
    downtime_type: str = "maintenance"  # maintenance | break | breakdown
    notes: Optional[str] = None


class DowntimeWindowResponse(DowntimeWindowCreate):
    id: UUID
    company_id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}


class CapacityResponse(BaseModel):
    work_center_id: UUID
    work_center_code: str
    work_center_name: str
    capacity_per_shift: Decimal
    scheduled_operations_minutes: Decimal
    available_minutes: Decimal
    utilization_percent: Decimal
    downtime_minutes: Decimal

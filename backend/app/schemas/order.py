# backend/app/schemas/order.py
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models.order import OrderStatus, PaymentStatus


class OrderItemCreate(BaseModel):
    product_id: Optional[UUID] = None
    product_name: str
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    discount_percent: float = Field(default=0, ge=0, le=100)


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: Optional[UUID]
    product_name: Optional[str] = None
    quantity: float
    unit_price: float
    discount_percent: float
    total: float

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    client_id: UUID
    warehouse_id: Optional[UUID] = None
    items: List[OrderItemCreate] = Field(..., min_length=1)
    delivery_date: Optional[datetime] = None
    delivery_address: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[UUID] = None
    is_vat_payer: bool = True
    payment_due_date: Optional[datetime] = None


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    delivery_date: Optional[datetime] = None
    delivery_address: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[UUID] = None
    is_vat_payer: Optional[bool] = None
    payment_due_date: Optional[datetime] = None


class OrderStatusChange(BaseModel):
    status: OrderStatus
    notes: Optional[str] = None
    warehouse_id: Optional[UUID] = None


class StockCheckItem(BaseModel):
    product_id: UUID
    product_name: str
    requested: float
    available: float
    reserved: float
    sufficient: bool


class StockCheckResponse(BaseModel):
    all_sufficient: bool
    items: List[StockCheckItem]


class OrderLifecycleTransition(BaseModel):
    from_status: str
    to_status: str
    label: str
    allowed: bool


class OrderLifecycleResponse(BaseModel):
    current_status: str
    available_transitions: List[OrderLifecycleTransition]
    all_statuses: List[str]


class PaymentUpdate(BaseModel):
    payment_status: PaymentStatus
    paid_amount: Optional[float] = None
    paid_at: Optional[datetime] = None
    notes: Optional[str] = None


class OrderResponse(BaseModel):
    id: UUID
    company_id: UUID
    client_id: UUID
    client_name: Optional[str] = None
    order_number: str
    status: str
    subtotal: float
    vat_amount: float
    total: float
    vat_rate: float = 0.18
    payment_status: str = "unpaid"
    paid_amount: float = 0
    payment_due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    delivery_date: Optional[datetime]
    delivery_address: Optional[str]
    notes: Optional[str]
    assigned_to: Optional[UUID]
    created_by: Optional[UUID]
    warehouse_id: Optional[UUID] = None
    warehouse_name: Optional[str] = None
    reservation_status: Optional[str] = None
    items: List[OrderItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderListResponse(BaseModel):
    id: UUID
    order_number: str
    client_name: Optional[str]
    status: str
    total: float
    payment_status: str = "unpaid"
    created_at: datetime
    assigned_to_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OrderStatusHistoryResponse(BaseModel):
    id: UUID
    status: str
    notes: Optional[str]
    changed_by: Optional[UUID]
    changed_by_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderTimelineEntry(BaseModel):
    id: UUID
    event_type: str  # "status_change", "payment_update", "note_added", "item_modified"
    status: Optional[str] = None
    payment_status: Optional[str] = None
    description: str
    notes: Optional[str] = None
    changed_by: Optional[UUID] = None
    changed_by_name: Optional[str] = None
    created_at: datetime


class InventoryReservationResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    warehouse_id: UUID
    warehouse_name: str
    quantity: Decimal
    status: str
    available_after_reservation: Decimal


class InvoiceCreate(BaseModel):
    order_id: UUID


class InvoiceResponse(BaseModel):
    id: UUID
    order_id: UUID
    invoice_number: str
    total: float
    pdf_url: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

"""Pydantic schemas for Point of Sale module."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class POSSessionCreate(BaseModel):
    name: str = Field(..., max_length=255)


class POSSessionResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    status: str
    opened_at: datetime
    closed_at: Optional[datetime] = None
    total_sales: float
    total_orders: int
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class POSOrderItemCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)


class POSOrderCreate(BaseModel):
    session_id: UUID
    client_id: Optional[UUID] = None
    payment_method: str = "cash"
    payment_reference: Optional[str] = None
    items: list[POSOrderItemCreate]


class POSOrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    quantity: float
    unit_price: float
    line_total: float

    model_config = {"from_attributes": True}


class POSOrderResponse(BaseModel):
    id: UUID
    company_id: UUID
    session_id: UUID
    client_id: Optional[UUID] = None
    order_number: str
    status: str
    subtotal: float
    vat_amount: float
    total: float
    payment_method: str
    payment_reference: Optional[str] = None
    created_at: datetime
    items: list[POSOrderItemResponse] = []

    model_config = {"from_attributes": True}

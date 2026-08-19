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
    discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    discount_amount: Optional[Decimal] = Field(None, ge=0)


class POSOrderCreate(BaseModel):
    session_id: UUID
    client_id: Optional[UUID] = None
    payment_method: str = "cash"
    payment_reference: Optional[str] = None
    items: list[POSOrderItemCreate]
    # Split payment: list of {method, amount, reference?, gift_card_id?}
    payments: Optional[list[dict]] = None
    # Order-level discount (percent or fixed amount)
    discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    discount_amount: Optional[Decimal] = Field(None, ge=0)
    # Cash rounding (1 tetri) — GE law: cash totals round to 0.01
    rounding_amount: Optional[Decimal] = Field(None)


class POSOrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    quantity: float
    unit_price: float
    discount_amount: float = 0
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
    discount_amount: float = 0
    rounding_amount: float = 0
    vat_amount: float
    total: float
    payment_method: str
    payment_reference: Optional[str] = None
    created_at: datetime
    items: list[POSOrderItemResponse] = []

    model_config = {"from_attributes": True}

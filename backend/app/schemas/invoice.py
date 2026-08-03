from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class InvoiceGenerate(BaseModel):
    order_id: UUID
    idempotency_key: str = Field(..., min_length=1, max_length=100)
    invoice_date: date
    due_date: date
    notes: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.due_date < self.invoice_date:
            raise ValueError("due_date invoice_date-ზე ადრე ვერ იქნება")
        return self


class InvoiceDraftItemUpdate(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=255)
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    discount_percent: Decimal = Field(Decimal("0"), ge=0, le=100)
    vat_rate: Decimal = Field(Decimal("0"), ge=0, le=100)


class InvoiceDraftUpdate(BaseModel):
    invoice_date: date
    due_date: date
    currency: str = Field(..., min_length=3, max_length=3)
    seller_name: str = Field(..., min_length=1, max_length=255)
    seller_identification_code: str = Field(..., min_length=1, max_length=50)
    seller_address: str = Field("", max_length=2000)
    seller_phone: str = Field("", max_length=50)
    seller_email: str = Field("", max_length=255)
    client_name: str = Field(..., min_length=1, max_length=255)
    client_identification_code: str = Field(..., min_length=1, max_length=50)
    client_address: str = Field("", max_length=2000)
    notes: str | None = Field(None, max_length=2000)
    items: list[InvoiceDraftItemUpdate] = Field(..., min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_draft(self):
        if self.due_date < self.invoice_date:
            raise ValueError("due_date invoice_date-ზე ადრე ვერ იქნება")
        self.currency = self.currency.upper()
        return self


class InvoiceItemResponse(BaseModel):
    id: UUID
    order_item_id: UUID | None
    product_id: UUID | None
    line_number: int
    product_name: str
    quantity: float
    unit_price: float
    discount_percent: float
    line_subtotal: float
    vat_rate: float
    vat_amount: float
    line_total: float


class InvoiceResponse(BaseModel):
    id: UUID
    company_id: UUID
    client_id: UUID
    order_id: UUID
    invoice_number: str
    status: str
    invoice_date: date
    due_date: date
    currency: str
    subtotal: float
    vat_amount: float
    total: float
    order_number: str
    seller_name: str
    seller_identification_code: str
    seller_address: str
    seller_phone: str
    seller_email: str
    client_name: str
    client_identification_code: str
    client_address: str
    notes: str | None
    download_url: str
    items: list[InvoiceItemResponse]
    created_at: datetime
    updated_at: datetime


class InvoiceListResponse(BaseModel):
    id: UUID
    order_id: UUID
    invoice_number: str
    status: str
    invoice_date: date
    due_date: date
    currency: str
    total: float
    order_number: str
    client_name: str
    client_identification_code: str
    download_url: str
    created_at: datetime

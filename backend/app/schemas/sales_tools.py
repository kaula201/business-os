"""Pricing + quotations + payment terms Pydantic schemas."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Price lists ──────────────────────────────────────────────────────────────

class PriceListItemCreate(BaseModel):
    product_id: UUID
    price: Decimal = Field(ge=0)
    min_quantity: Decimal = Field(default=Decimal("1"), ge=0)
    currency: str | None = Field(default=None, max_length=3, description="ვალუტის მიხედვით ფასი (override)")
    margin_percent: Decimal | None = Field(default=None, ge=0, le=100, description="item-ის მარჟა")


class PriceListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    currency: str = Field(default="GEL", max_length=3)
    is_default: bool = False
    description: str | None = None
    items: list[PriceListItemCreate] = []
    # PriceList 2.0 — rule engine
    valid_from: date | None = None
    valid_until: date | None = None
    segment_id: UUID | None = None
    pricing_method: str = Field(default="fixed", pattern="^(fixed|cost_plus_markup)$")
    markup_percent: Decimal = Field(default=Decimal("0"), ge=0)
    min_margin_percent: Decimal | None = Field(default=None, ge=0, le=100)
    approval_required: bool = False


class PriceListUpdate(BaseModel):
    name: str | None = None
    currency: str | None = None
    is_default: bool | None = None
    description: str | None = None
    is_active: bool | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    segment_id: UUID | None = None
    pricing_method: str | None = Field(default=None, pattern="^(fixed|cost_plus_markup)$")
    markup_percent: Decimal | None = Field(default=None, ge=0)
    min_margin_percent: Decimal | None = Field(default=None, ge=0, le=100)
    approval_required: bool | None = None


class PriceListItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    price: float
    min_quantity: float
    currency: str | None = None
    margin_percent: float | None = None


class PriceListResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    currency: str
    is_default: bool
    description: str | None
    is_active: bool
    items: list[PriceListItemResponse] = []
    created_at: datetime
    updated_at: datetime
    # PriceList 2.0 — rule engine
    valid_from: date | None = None
    valid_until: date | None = None
    segment_id: UUID | None = None
    segment_name: str | None = None
    pricing_method: str = "fixed"
    markup_percent: float = 0
    min_margin_percent: float | None = None
    approval_required: bool = False


# ── Quotations ───────────────────────────────────────────────────────────────

class QuotationItemCreate(BaseModel):
    product_id: UUID | None = None
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    is_optional: bool = False
    config: dict | None = None


class QuotationCreate(BaseModel):
    client_id: UUID
    quotation_date: date
    valid_until: date | None = None
    currency: str = Field(default="GEL", max_length=3)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    notes: str | None = None
    items: list[QuotationItemCreate] = Field(min_length=1)


class QuotationStatusUpdate(BaseModel):
    status: str = Field(pattern="^(sent|accepted|rejected|expired)$")


class QuotationItemResponse(BaseModel):
    id: UUID
    product_id: UUID | None
    line_number: int
    description: str
    quantity: float
    unit_price: float
    discount_percent: float
    line_total: float
    is_optional: bool = False
    config: dict | None = None


class QuotationResponse(BaseModel):
    id: UUID
    company_id: UUID
    client_id: UUID
    client_name: str | None = None
    quotation_number: str
    quotation_date: date
    valid_until: date | None
    status: str
    currency: str
    subtotal: float
    vat_amount: float
    total: float
    discount_percent: float
    notes: str | None
    order_id: UUID | None
    items: list[QuotationItemResponse] = []
    created_at: datetime
    updated_at: datetime
    # Quotation 2.0
    version_number: int = 1
    approval_required: bool = False
    approval_request_id: UUID | None = None
    signed_at: datetime | None = None
    signed_by: str | None = None
    signature_hash: str | None = None
    signature_method: str | None = None
    portal_token: str | None = None
    portal_responded_at: datetime | None = None


class QuotationVersionResponse(BaseModel):
    id: UUID
    version_number: int
    status: str
    subtotal: float
    vat_amount: float
    total: float
    discount_percent: float
    items_snapshot: list = []
    notes: str | None
    change_reason: str | None
    created_at: datetime


class QuotationUpdate(BaseModel):
    """Full revision — creates a new version snapshot."""
    valid_until: date | None = None
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    notes: str | None = None
    items: list[QuotationItemCreate] = Field(min_length=1)
    change_reason: str | None = None


class QuotationSignRequest(BaseModel):
    signer_name: str = Field(min_length=1, max_length=255)
    method: str = Field(default="manual", pattern="^(manual|portal)$")


class PortalRespondRequest(BaseModel):
    action: str = Field(pattern="^(accept|reject)$")
    signer_name: str | None = None


# ── Payment terms ────────────────────────────────────────────────────────────

class PaymentTermCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    days: int = Field(default=0, ge=0, le=3650)
    description: str | None = None


class PaymentTermUpdate(BaseModel):
    name: str | None = None
    days: int | None = Field(default=None, ge=0, le=3650)
    description: str | None = None
    is_active: bool | None = None


class PaymentTermResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    days: int
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

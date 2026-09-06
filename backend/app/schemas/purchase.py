from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


# ── Supplier Schemas ─────────────────────────────────────────────────

class SupplierCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    identification_code: str | None = Field(default=None, max_length=50)
    is_vat_payer: bool = False
    fiscal_position_id: UUID | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    bank_account: str | None = Field(default=None, max_length=100)
    payment_terms_days: int = Field(default=0, ge=0, le=3650)
    notes: str | None = None
    category: str | None = Field(default=None, max_length=100)
    risk_level: str = Field(default="low", max_length=20)
    risk_score: int | None = Field(default=None, ge=0, le=100)
    is_blacklisted: bool = False
    blacklist_reason: str | None = None


class SupplierUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    identification_code: str | None = Field(default=None, max_length=50)
    is_vat_payer: bool | None = None
    fiscal_position_id: UUID | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    bank_account: str | None = Field(default=None, max_length=100)
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    notes: str | None = None
    is_active: bool | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    category: str | None = Field(default=None, max_length=100)
    risk_level: str | None = Field(default=None, max_length=20)
    risk_score: int | None = Field(default=None, ge=0, le=100)
    is_blacklisted: bool | None = None
    blacklist_reason: str | None = None


class SupplierBankDetailCreate(BaseModel):
    bank_name: str = Field(..., min_length=1, max_length=150)
    account_name: str = Field(..., min_length=1, max_length=150)
    iban: str = Field(..., min_length=1, max_length=64)
    currency: str = Field(default="GEL", max_length=3)
    is_primary: bool = False
    notes: str | None = None


class SupplierBankDetailUpdate(BaseModel):
    bank_name: str | None = Field(default=None, min_length=1, max_length=150)
    account_name: str | None = Field(default=None, min_length=1, max_length=150)
    iban: str | None = Field(default=None, min_length=1, max_length=64)
    currency: str | None = Field(default=None, max_length=3)
    is_primary: bool | None = None
    is_active: bool | None = None
    notes: str | None = None


class SupplierBankDetailResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    bank_name: str
    account_name: str
    iban_masked: str = "****"
    currency: str
    is_primary: bool
    is_active: bool
    notes: str | None
    approval_status: str = "pending"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Mask the IBAN for secure display — show only last 4 chars."""
        data = super().model_validate(obj, **kwargs)
        if obj.iban and len(obj.iban) > 4:
            data.iban_masked = "****" + obj.iban[-4:]
        else:
            data.iban_masked = "****"
        return data


class SupplierRatingCreate(BaseModel):
    rating: float = Field(..., ge=0, le=5)
    comment: str | None = None


class SupplierRatingHistoryResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    rating: float
    comment: str | None
    changed_by: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierResponse(BaseModel):
    id: UUID
    code: str
    name: str
    identification_code: str | None
    is_vat_payer: bool
    fiscal_position_id: UUID | None = None
    contact_name: str | None
    phone: str | None
    email: str | None
    address: str | None
    bank_account: str | None
    payment_terms_days: int
    notes: str | None
    is_active: bool
    rating: float | None
    total_purchase_amount: float
    last_purchase_date: date | None
    category: str | None = None
    risk_level: str = "low"
    risk_score: int | None = None
    is_blacklisted: bool = False
    blacklist_reason: str | None = None
    onboarding_status: str = "pending"
    purchase_order_count: int = 0
    outstanding_payable_count: int = 0
    outstanding_payable_amount: float = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierDetailResponse(SupplierResponse):
    """Full supplier detail including bank details, rating history, and quick links."""
    bank_details: list[SupplierBankDetailResponse] = []
    rating_history: list[SupplierRatingHistoryResponse] = []
    purchase_orders_url: str = ""
    payables_url: str = ""


class PurchaseOrderItemCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(..., gt=0, max_digits=18, decimal_places=3)
    unit_price: Decimal = Field(..., ge=0, max_digits=18, decimal_places=4)
    discount_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=7, decimal_places=4
    )
    vat_rate: Decimal = Field(
        default=Decimal("18"), ge=0, le=100, max_digits=7, decimal_places=4
    )


class PurchaseOrderCreate(BaseModel):
    supplier_id: UUID
    warehouse_id: UUID
    expected_delivery_date: date | None = None
    notes: str | None = None
    items: list[PurchaseOrderItemCreate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def products_must_be_unique(self):
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("ერთი პროდუქტი Purchase Order-ში ერთხელ უნდა იყოს")
        return self


class PurchaseOrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    quantity: float
    received_quantity: float
    billed_quantity: float
    remaining_quantity: float
    remaining_to_bill: float
    unit_price: float
    discount_percent: float
    vat_rate: float
    line_subtotal: float
    vat_amount: float
    line_total: float


class PurchaseOrderResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    warehouse_id: UUID
    warehouse_name: str
    purchase_order_number: str
    status: str
    version: int
    expected_delivery_date: date | None
    subtotal: float
    vat_amount: float
    total: float
    notes: str | None
    approved_at: datetime | None
    approved_by: UUID | None
    required_approval_role: Literal["manager", "admin"]
    items: list[PurchaseOrderItemResponse]
    created_at: datetime
    updated_at: datetime


class PurchaseOrderStatusChange(BaseModel):
    status: Literal["draft", "approved", "partially_received", "received", "cancelled"]
    notes: str | None = None


class PurchaseOrderHistoryResponse(BaseModel):
    id: UUID
    status: str
    notes: str | None
    changed_by: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoodsReceiptItemCreate(BaseModel):
    purchase_order_item_id: UUID
    quantity: Decimal = Field(..., gt=0, max_digits=18, decimal_places=3)


class GoodsReceiptCreate(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=100)
    notes: str | None = None
    items: list[GoodsReceiptItemCreate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def purchase_order_items_must_be_unique(self):
        item_ids = [item.purchase_order_item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("ერთი Purchase Order item receipt-ში ერთხელ უნდა იყოს")
        return self


class GoodsReceiptItemResponse(BaseModel):
    id: UUID
    purchase_order_item_id: UUID
    product_id: UUID
    product_name: str
    quantity: float


class GoodsReceiptResponse(BaseModel):
    id: UUID
    purchase_order_id: UUID
    receipt_number: str
    warehouse_id: UUID
    warehouse_name: str
    idempotency_key: str
    status: str
    purchase_order_status: str
    notes: str | None
    received_at: datetime
    quality_status: str | None = None
    quality_notes: str | None = None
    items: list[GoodsReceiptItemResponse]


# ── Three-Way Matching ──────────────────────────────────────────────

class ThreeWayMatchItem(BaseModel):
    purchase_order_item_id: UUID
    product_name: str
    ordered_quantity: float
    received_quantity: float
    billed_quantity: float
    ordered_amount: float
    billed_amount: float
    quantity_match: Literal["ok", "under_received", "over_received", "under_billed", "over_billed"]
    price_match: Literal["ok", "price_mismatch"]
    overall: Literal["match", "mismatch"]


class ThreeWayMatchSummary(BaseModel):
    purchase_order_id: UUID
    purchase_order_number: str
    supplier_name: str
    total_ordered: float
    total_received: float
    total_billed: float
    total_ordered_amount: float
    total_billed_amount: float
    match_status: Literal["full_match", "partial_match", "mismatch"]
    items: list[ThreeWayMatchItem]


# ── Workflow Tracking ────────────────────────────────────────────────

class WorkflowStep(BaseModel):
    step: str
    label: str
    status: Literal["completed", "active", "pending", "skipped"]
    timestamp: datetime | None = None
    reference: str | None = None
    reference_id: UUID | None = None


class PurchaseWorkflowResponse(BaseModel):
    purchase_order_id: UUID
    purchase_order_number: str
    supplier_name: str
    total: float
    status: str
    steps: list[WorkflowStep]


# ── Approval Limit Visualization ────────────────────────────────────

class ApprovalLimitInfo(BaseModel):
    manager_approval_limit: float
    current_po_total: float
    requires_admin: bool
    po_count_within_limit: int
    po_count_exceeding_limit: int
    po_count_total: int

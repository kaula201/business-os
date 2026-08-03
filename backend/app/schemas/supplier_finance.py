from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SupplierInvoiceItemCreate(BaseModel):
    purchase_order_item_id: UUID
    quantity: Decimal = Field(..., gt=0, max_digits=18, decimal_places=3)
    unit_price: Decimal = Field(..., ge=0, max_digits=18, decimal_places=4)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    vat_rate: Decimal = Field(default=Decimal("18"), ge=0, le=100)


class SupplierInvoiceCreate(BaseModel):
    supplier_id: UUID
    purchase_order_id: UUID
    supplier_invoice_number: str = Field(..., min_length=1, max_length=100)
    invoice_date: date
    due_date: date
    notes: str | None = None
    items: list[SupplierInvoiceItemCreate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_invoice(self):
        if self.due_date < self.invoice_date:
            raise ValueError("გადახდის ვადა invoice date-ზე ადრე ვერ იქნება")
        item_ids = [item.purchase_order_item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("ერთი Purchase Order item invoice-ში ერთხელ უნდა იყოს")
        return self


class SupplierPaymentCreate(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    payment_date: date
    payment_method: Literal["bank_transfer", "cash", "card", "other"]
    reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    allow_overpayment: bool = Field(default=False, description="Allow payment exceeding outstanding amount")
    currency_code: str | None = Field(default=None, max_length=3, description="Payment currency (defaults to payable currency)")


class SupplierCreditNoteCreate(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=100)
    supplier_credit_note_number: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    credit_date: date
    reason: str = Field(..., min_length=1, max_length=2000)
    currency_code: str | None = Field(default=None, max_length=3, description="Credit note currency (defaults to payable currency)")
    exchange_rate: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6, description="Exchange rate if different currency")


class SupplierPaymentReversalCreate(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=100)
    reason: str = Field(..., min_length=1, max_length=2000)


class SupplierPaymentReversalResponse(BaseModel):
    id: UUID
    amount: float
    reason: str
    created_at: datetime


class SupplierPaymentResponse(BaseModel):
    id: UUID
    amount: float
    payment_date: date
    payment_method: str
    reference: str | None
    notes: str | None
    is_reversed: bool
    reversal: SupplierPaymentReversalResponse | None
    created_at: datetime


class SupplierCreditNoteResponse(BaseModel):
    id: UUID
    supplier_credit_note_number: str
    amount: float
    credit_date: date
    reason: str
    currency_code: str | None = None
    exchange_rate: float | None = None
    created_at: datetime


class SupplierOverpaymentResponse(BaseModel):
    id: UUID
    amount: float
    remaining_amount: float
    currency_code: str
    exchange_rate: float
    notes: str | None
    created_at: datetime


class SupplierPayableResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    supplier_invoice_id: UUID
    internal_invoice_number: str
    supplier_invoice_number: str
    due_date: date
    original_amount: float
    paid_amount: float
    credited_amount: float
    overpaid_amount: float
    outstanding_amount: float
    currency_code: str
    exchange_rate: float
    status: str
    days_overdue: int
    payments: list[SupplierPaymentResponse]
    credit_notes: list[SupplierCreditNoteResponse]
    overpayments: list[SupplierOverpaymentResponse]
    created_at: datetime
    updated_at: datetime


class SupplierInvoiceItemResponse(BaseModel):
    id: UUID
    purchase_order_item_id: UUID
    product_id: UUID
    product_name: str
    quantity: float
    unit_price: float
    discount_percent: float
    vat_rate: float
    line_subtotal: float
    vat_amount: float
    line_total: float
    matching_status: str
    match_issue: str | None


class SupplierInvoiceResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    purchase_order_id: UUID
    purchase_order_number: str
    internal_invoice_number: str
    supplier_invoice_number: str
    invoice_date: date
    due_date: date
    status: str
    matching_status: str
    match_issues: list[str]
    subtotal: float
    vat_amount: float
    total: float
    notes: str | None
    approved_at: datetime | None
    items: list[SupplierInvoiceItemResponse]
    payable: SupplierPayableResponse | None
    created_at: datetime
    updated_at: datetime


class SupplierInvoiceStatusChange(BaseModel):
    status: Literal["approved", "cancelled"]
    notes: str | None = None


# ── Tolerance settings ──────────────────────────────────────────────────────

class SupplierInvoiceToleranceCreate(BaseModel):
    quantity_tolerance_percent: Decimal = Field(default=Decimal("5"), ge=0, le=100)
    price_tolerance_percent: Decimal = Field(default=Decimal("2"), ge=0, le=100)
    amount_tolerance: Decimal = Field(default=Decimal("1"), ge=0, max_digits=18, decimal_places=2)
    enable_duplicate_detection: bool = True
    duplicate_lookback_days: int = Field(default=90, ge=1, le=365)


class SupplierInvoiceToleranceResponse(BaseModel):
    id: UUID
    quantity_tolerance_percent: float
    price_tolerance_percent: float
    amount_tolerance: float
    enable_duplicate_detection: bool
    duplicate_lookback_days: int
    created_at: datetime
    updated_at: datetime


# ── Duplicate invoice detection ────────────────────────────────────────────

class DuplicateInvoiceCheck(BaseModel):
    supplier_id: UUID
    supplier_invoice_number: str = Field(..., min_length=1, max_length=100)
    invoice_date: date
    total: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)


class DuplicateInvoiceResult(BaseModel):
    is_duplicate: bool
    confidence: str  # "high", "medium", "low"
    matched_invoices: list[dict]
    reason: str | None = None


# ── Overpayment application ────────────────────────────────────────────────

class OverpaymentApplyCreate(BaseModel):
    overpayment_id: UUID
    payable_id: UUID
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    notes: str | None = None


# ── Credit note with currency difference ───────────────────────────────────

class SupplierCreditNoteCurrencyDiffResponse(BaseModel):
    id: UUID
    credit_note_id: UUID
    payable_currency: str
    credit_note_currency: str
    exchange_rate: float
    amount_in_payable_currency: float
    amount_in_credit_note_currency: float
    currency_difference: float
    created_at: datetime

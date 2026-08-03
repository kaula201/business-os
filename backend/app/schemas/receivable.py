from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CustomerPaymentCreate(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    payment_date: date
    payment_method: str = Field(min_length=1, max_length=30)
    reference: str = Field(default="", max_length=255)
    notes: str | None = None


class CustomerPaymentReversalCreate(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1)


class CustomerCreditNoteCreate(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=100)
    credit_note_number: str = Field(min_length=1, max_length=50)
    amount: float = Field(gt=0)
    credit_date: date
    reason: str = Field(min_length=1)


class CustomerBankReconciliationCreate(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=100)
    customer_receivable_id: UUID
    amount: float = Field(gt=0)
    notes: str | None = None


class CustomerBankReconciliationReversalCreate(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1)


class CustomerPaymentResponse(BaseModel):
    id: UUID
    receivable_id: UUID
    amount: float
    payment_date: date
    payment_method: str
    reference: str
    notes: str | None
    status: str
    reversal_reason: str | None = None
    created_at: datetime


class CustomerCreditNoteResponse(BaseModel):
    id: UUID
    receivable_id: UUID
    credit_note_number: str
    amount: float
    credit_date: date
    reason: str
    created_at: datetime


class CustomerReceivableResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    invoice_number: str
    client_id: UUID
    client_name: str
    currency: str
    original_amount: float
    paid_amount: float
    credited_amount: float
    outstanding_amount: float
    due_date: date
    overdue_days: int
    status: str
    payments: list[CustomerPaymentResponse] = []
    credit_notes: list[CustomerCreditNoteResponse] = []
    created_at: datetime


class CustomerPaymentResult(BaseModel):
    receivable: CustomerReceivableResponse
    payment: CustomerPaymentResponse


class CustomerCreditNoteResult(BaseModel):
    receivable: CustomerReceivableResponse
    credit_note: CustomerCreditNoteResponse


class CustomerBankReconciliationResponse(BaseModel):
    id: UUID
    bank_transaction_id: UUID
    customer_receivable_id: UUID
    customer_payment_id: UUID
    amount: float
    status: str
    notes: str | None
    reversal_reason: str | None
    reversed_at: datetime | None
    created_at: datetime


class CustomerBankReconciliationResult(BaseModel):
    transaction: dict
    receivable: CustomerReceivableResponse
    reconciliation: CustomerBankReconciliationResponse

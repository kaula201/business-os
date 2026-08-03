from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.supplier_finance import SupplierPayableResponse


class BankAccountCreate(BaseModel):
    bank_name: str = Field(..., min_length=1, max_length=150)
    account_name: str = Field(..., min_length=1, max_length=150)
    iban: str = Field(..., min_length=6, max_length=64)
    currency: str = Field("GEL", min_length=3, max_length=3)


class BankAccountResponse(BaseModel):
    id: UUID
    bank_name: str
    account_name: str
    iban: str
    currency: str
    status: str
    created_at: datetime


class BankStatementImportCreate(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=100)
    filename: str = Field(..., min_length=1, max_length=255)
    csv_content: str = Field(..., min_length=1, max_length=5_000_000)


class BankStatementImportResponse(BaseModel):
    id: UUID
    bank_account_id: UUID
    filename: str
    transaction_count: int
    debit_total: float
    credit_total: float
    created_at: datetime


class BankTransactionResponse(BaseModel):
    id: UUID
    bank_account_id: UUID
    bank_account_name: str
    transaction_date: date
    reference: str
    description: str
    counterparty: str
    amount: float
    matched_amount: float
    unmatched_amount: float
    direction: str
    currency: str
    status: str
    created_at: datetime


class BankReconciliationCreate(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=100)
    supplier_payable_id: UUID
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    notes: str | None = Field(None, max_length=2000)


class BankReconciliationReversalCreate(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=100)
    reason: str = Field(..., min_length=1, max_length=2000)


class BankReconciliationResponse(BaseModel):
    id: UUID
    bank_transaction_id: UUID
    supplier_payable_id: UUID
    supplier_payment_id: UUID
    amount: float
    status: str
    notes: str | None
    reversal_reason: str | None
    reversed_at: datetime | None
    created_at: datetime


class BankReconciliationListResponse(BankReconciliationResponse):
    transaction_reference: str
    supplier_name: str
    supplier_invoice_number: str


class BankReconciliationResult(BaseModel):
    transaction: BankTransactionResponse
    payable: SupplierPayableResponse
    reconciliation: BankReconciliationResponse

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class AnalyticAccountCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=255)
    account_type: str = Field("cost_center", max_length=30)
    notes: str | None = None

class AnalyticAccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None
    notes: str | None = None

class AnalyticAccountResponse(BaseModel):
    id: UUID
    company_id: UUID
    code: str
    name: str
    account_type: str
    is_active: bool
    notes: str | None
    income_total: float = 0
    expense_total: float = 0
    balance: float = 0
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AnalyticEntryCreate(BaseModel):
    analytic_account_id: UUID
    gl_account_id: UUID | None = None
    project_id: UUID | None = None
    entry_date: date
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    direction: str = Field(..., pattern="^(income|expense)$")
    reference: str | None = Field(None, max_length=100)


class AnalyticEntryResponse(BaseModel):
    id: UUID
    analytic_account_id: UUID
    analytic_account_name: str
    gl_account_id: UUID | None
    project_id: UUID | None
    entry_date: date
    description: str
    amount: float
    direction: str
    reference: str | None
    created_at: datetime


class AnalyticAllocationRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source_gl_account_id: UUID
    target_analytic_account_id: UUID
    allocation_percent: Decimal = Field(..., gt=0, le=100, max_digits=5, decimal_places=2)
    period: str | None = Field(None, max_length=7, pattern=r"^\d{4}-\d{2}$")


class AnalyticAllocationRuleResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    source_gl_account_id: UUID
    source_gl_account_code: str = ""
    source_gl_account_name: str = ""
    target_analytic_account_id: UUID
    target_analytic_account_code: str = ""
    target_analytic_account_name: str = ""
    allocation_percent: float
    period: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GLReconciliationItem(BaseModel):
    gl_account_id: UUID
    gl_account_code: str
    gl_account_name: str
    gl_balance: float
    analytic_balance: float
    difference: float

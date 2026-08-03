from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)


class ExpenseCategoryResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpenseCreate(BaseModel):
    category_id: UUID | None = None
    project_id: UUID | None = None
    expense_date: date
    description: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    currency: str = Field("GEL", min_length=3, max_length=3)
    tax_type: str | None = Field(default=None, max_length=30)
    tax_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    receipt_url: str | None = Field(default=None, max_length=500)
    notes: str | None = None


class ExpenseUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    tax_type: str | None = Field(default=None, max_length=30)
    tax_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    notes: str | None = None
    receipt_url: str | None = None


class ExpenseResponse(BaseModel):
    id: UUID
    company_id: UUID
    employee_id: UUID
    employee_name: str
    category_id: UUID | None
    category_name: str | None
    project_id: UUID | None
    expense_date: date
    description: str
    amount: float
    currency: str
    tax_type: str | None
    tax_amount: float | None
    status: str
    receipt_url: str | None
    notes: str | None
    approved_by: UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

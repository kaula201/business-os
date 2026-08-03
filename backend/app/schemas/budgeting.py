from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BudgetPlanCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    fiscal_year: int = Field(..., ge=2020, le=2100)
    period_type: str = Field("monthly", max_length=20)
    scenario: str = Field("base", max_length=50)
    notes: str | None = None


class BudgetPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=20)
    scenario: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class BudgetLineCreate(BaseModel):
    gl_account_id: UUID
    project_id: UUID | None = None
    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    planned_amount: Decimal = Field(..., ge=0, max_digits=18, decimal_places=2)
    notes: str | None = None


class BudgetLineResponse(BaseModel):
    id: UUID
    plan_id: UUID
    gl_account_id: UUID
    gl_account_code: str
    gl_account_name: str
    project_id: UUID | None
    period: str
    planned_amount: float
    actual_amount: float
    variance: float
    variance_percent: float | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetPlanResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    fiscal_year: int
    period_type: str
    scenario: str
    status: str
    notes: str | None
    total_planned: float
    total_actual: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetLineCreateBatch(BaseModel):
    lines: list[BudgetLineCreate]


class BudgetPeriodSummary(BaseModel):
    """Per-period breakdown for a budget plan."""
    period: str
    planned: float
    actual: float
    variance: float
    variance_percent: float | None


class BudgetScenarioResponse(BaseModel):
    """Budget scenario summary."""
    id: UUID
    name: str
    scenario: str
    fiscal_year: int
    total_planned: float
    total_actual: float
    status: str

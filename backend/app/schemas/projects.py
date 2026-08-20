"""Projects schemas."""
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ── Milestone Schemas ──────────────────────────────────────────────────────────

class MilestoneCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    target_date: Optional[date] = None
    status: str = Field(default="pending", max_length=20)
    completion_percent: Decimal = Field(default=Decimal("0"), max_digits=5, decimal_places=2)
    owner_id: Optional[UUID] = None
    sort_order: int = Field(default=0)


class MilestoneUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    target_date: Optional[date] = None
    completed_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=20)
    completion_percent: Optional[Decimal] = Field(None, max_digits=5, decimal_places=2)
    owner_id: Optional[UUID] = None
    sort_order: Optional[int] = None


class MilestoneResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: Optional[str] = None
    target_date: Optional[date] = None
    completed_date: Optional[date] = None
    status: str
    completion_percent: Decimal
    owner_id: Optional[UUID] = None
    owner_name: Optional[str] = None
    sort_order: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Project Schemas ────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    manager_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget_amount: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    spent_amount: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    revenue_amount: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    budget_plan_id: Optional[UUID] = None
    notes: Optional[str] = None


class ProjectUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    manager_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    status: Optional[str] = Field(None, max_length=20)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    completion_percent: Optional[Decimal] = Field(None, max_digits=5, decimal_places=2)
    budget_amount: Optional[Decimal] = Field(None, max_digits=14, decimal_places=2)
    spent_amount: Optional[Decimal] = Field(None, max_digits=14, decimal_places=2)
    revenue_amount: Optional[Decimal] = Field(None, max_digits=14, decimal_places=2)
    budget_plan_id: Optional[UUID] = None
    notes: Optional[str] = None


class ProjectResponse(BaseModel):
    id: UUID
    company_id: UUID
    code: str
    name: str
    description: Optional[str] = None
    manager_id: Optional[UUID] = None
    manager_name: Optional[str] = None
    owner_id: Optional[UUID] = None
    owner_name: Optional[str] = None
    status: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    completion_percent: Decimal
    budget_amount: Decimal
    spent_amount: Decimal
    revenue_amount: Decimal
    budget_plan_id: Optional[UUID] = None
    budget_plan_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectResponse):
    """Full project detail including milestones and linked tasks."""
    milestones: list[MilestoneResponse] = []
    task_count: int = 0
    completed_task_count: int = 0
    profitability: Optional[Decimal] = None  # budget - spent
    profitability_percent: Optional[Decimal] = None  # (budget - spent) / budget * 100

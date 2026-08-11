"""Sales teams, targets, commissions Pydantic schemas."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Sales teams ──────────────────────────────────────────────────────────────

class SalesTeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    manager_id: UUID | None = None
    description: str | None = None


class SalesTeamUpdate(BaseModel):
    name: str | None = None
    manager_id: UUID | None = None
    description: str | None = None
    is_active: bool | None = None


class SalesTeamResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    manager_id: UUID | None
    description: str | None
    is_active: bool
    member_count: int = 0
    created_at: datetime
    updated_at: datetime


class SalesTeamMemberCreate(BaseModel):
    user_id: UUID


class SalesTeamMemberResponse(BaseModel):
    id: UUID
    team_id: UUID
    user_id: UUID
    user_name: str | None = None


# ── Sales targets ────────────────────────────────────────────────────────────

class SalesTargetCreate(BaseModel):
    period: str = Field(pattern=r"^\d{4}-\d{2}$")  # YYYY-MM
    team_id: UUID | None = None
    owner_id: UUID | None = None
    target_amount: Decimal = Field(ge=0)


class SalesTargetUpdate(BaseModel):
    target_amount: Decimal | None = Field(default=None, ge=0)
    achieved_amount: Decimal | None = Field(default=None, ge=0)


class SalesTargetResponse(BaseModel):
    id: UUID
    company_id: UUID
    period: str
    team_id: UUID | None
    owner_id: UUID | None
    target_amount: float
    achieved_amount: float
    progress_percent: float = 0
    created_at: datetime
    updated_at: datetime


# ── Commissions ──────────────────────────────────────────────────────────────

class CommissionRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    team_id: UUID | None = None
    owner_id: UUID | None = None
    product_category_id: UUID | None = None
    rate_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    fixed_amount: Decimal = Field(default=Decimal("0"), ge=0)


class CommissionRuleUpdate(BaseModel):
    name: str | None = None
    team_id: UUID | None = None
    owner_id: UUID | None = None
    product_category_id: UUID | None = None
    rate_percent: Decimal | None = Field(default=None, ge=0, le=100)
    fixed_amount: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class CommissionRuleResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    team_id: UUID | None
    owner_id: UUID | None
    product_category_id: UUID | None
    rate_percent: float
    fixed_amount: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CommissionAccrualResponse(BaseModel):
    id: UUID
    company_id: UUID
    rule_id: UUID
    order_id: UUID
    owner_id: UUID | None
    team_id: UUID | None
    base_amount: float
    commission_amount: float
    status: str
    paid_at: datetime | None
    created_at: datetime

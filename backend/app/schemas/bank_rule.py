"""Bank reconciliation rules Pydantic schemas."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class BankReconciliationRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    rule_type: str = Field(pattern="^(amount_date|description_contains|counterparty_equals|reference_equals)$")
    action: str = Field(default="categorize", pattern="^(auto_reconcile|categorize)$")
    match_text: str | None = None
    match_amount: Decimal | None = None
    date_window_days: int = Field(default=7, ge=0, le=365)
    direction: str = Field(default="any", pattern="^(in|out|any)$")
    gl_account_id: UUID | None = None
    gl_description: str | None = None
    priority: int = Field(default=100, ge=0, le=10000)


class BankReconciliationRuleUpdate(BaseModel):
    name: str | None = None
    rule_type: str | None = Field(default=None, pattern="^(amount_date|description_contains|counterparty_equals|reference_equals)$")
    action: str | None = Field(default=None, pattern="^(auto_reconcile|categorize)$")
    match_text: str | None = None
    match_amount: Decimal | None = None
    date_window_days: int | None = Field(default=None, ge=0, le=365)
    direction: str | None = Field(default=None, pattern="^(in|out|any)$")
    gl_account_id: UUID | None = None
    gl_description: str | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None


class BankReconciliationRuleResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    rule_type: str
    action: str
    match_text: str | None
    match_amount: float | None
    date_window_days: int
    direction: str
    gl_account_id: UUID | None
    gl_description: str | None
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BankRulesApplyResponse(BaseModel):
    matched: int
    categorized: int
    skipped: int

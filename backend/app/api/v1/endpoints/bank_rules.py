"""Bank reconciliation rules API — CRUD + apply to unmatched transactions."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.bank_rule import BankReconciliationRule
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.bank_rule import (
    BankReconciliationRuleCreate,
    BankReconciliationRuleResponse,
    BankReconciliationRuleUpdate,
    BankRulesApplyResponse,
)
from app.services.bank_rules import apply_rules

router = APIRouter(prefix="/banking/reconciliation-rules", tags=["ბანკი — შეჯერების წესები"])


def require_finance_role(user: User) -> None:
    if user.role not in (User.Role.ADMIN, User.Role.ACCOUNTANT):
        raise HTTPException(status_code=403, detail="ფინანსური ოპერაციები ხელმისაწვდომია მხოლოდ ადმინის/ბუღალტერისთვის")


def _to_response(r: BankReconciliationRule) -> BankReconciliationRuleResponse:
    return BankReconciliationRuleResponse(
        id=r.id, company_id=r.company_id, name=r.name, rule_type=r.rule_type,
        action=r.action, match_text=r.match_text,
        match_amount=float(r.match_amount) if r.match_amount is not None else None,
        date_window_days=r.date_window_days, direction=r.direction,
        gl_account_id=r.gl_account_id, gl_description=r.gl_description,
        priority=r.priority, is_active=r.is_active, created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("/", response_model=ResponseBase[PaginatedResponse[BankReconciliationRuleResponse]])
async def list_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    filters = [BankReconciliationRule.company_id == current_user.company_id]
    if is_active is not None:
        filters.append(BankReconciliationRule.is_active == is_active)
    total = (await db.execute(select(func.count(BankReconciliationRule.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(BankReconciliationRule)
            .where(*filters)
            .order_by(BankReconciliationRule.priority.asc(), BankReconciliationRule.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[_to_response(r) for r in rows],
    ))


@router.post("/", response_model=BankReconciliationRuleResponse, status_code=201)
async def create_rule(
    data: BankReconciliationRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    # Validate GL account for categorize rules
    if data.action == "categorize":
        if data.gl_account_id is None:
            raise HTTPException(status_code=400, detail="categorize წესს gl_account_id სჭირდება")
        from app.models.gl import GLAccount
        account = (
            await db.execute(select(GLAccount).where(
                GLAccount.id == data.gl_account_id,
                GLAccount.company_id == current_user.company_id,
            ))
        ).scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=400, detail="GL ანგარიში ვერ მოიძებნა")

    rule = BankReconciliationRule(
        company_id=current_user.company_id,
        name=data.name,
        rule_type=data.rule_type,
        action=data.action,
        match_text=data.match_text,
        match_amount=data.match_amount,
        date_window_days=data.date_window_days,
        direction=data.direction,
        gl_account_id=data.gl_account_id,
        gl_description=data.gl_description,
        priority=data.priority,
        created_by=current_user.id,
    )
    db.add(rule)
    await db.flush()
    add_audit(db, current_user, "bank_rule.created", "bank_reconciliation_rule", rule.id, {"name": rule.name})
    await db.commit()
    await db.refresh(rule)
    return _to_response(rule)


@router.patch("/{rule_id}", response_model=BankReconciliationRuleResponse)
async def update_rule(
    rule_id: uuid.UUID,
    data: BankReconciliationRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    rule = (
        await db.execute(select(BankReconciliationRule).where(
            BankReconciliationRule.id == rule_id,
            BankReconciliationRule.company_id == current_user.company_id,
        ))
    ).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="წესი ვერ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    add_audit(db, current_user, "bank_rule.updated", "bank_reconciliation_rule", rule.id, {"name": rule.name})
    await db.commit()
    await db.refresh(rule)
    return _to_response(rule)


@router.delete("/{rule_id}", response_model=dict)
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    rule = (
        await db.execute(select(BankReconciliationRule).where(
            BankReconciliationRule.id == rule_id,
            BankReconciliationRule.company_id == current_user.company_id,
        ))
    ).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="წესი ვერ მოიძებნა")
    await db.delete(rule)
    add_audit(db, current_user, "bank_rule.deleted", "bank_reconciliation_rule", rule.id, {"name": rule.name})
    await db.commit()
    return {"message": "წესი წაშლილია"}


@router.post("/apply", response_model=BankRulesApplyResponse)
async def apply_all_rules(
    on_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply all active rules to unmatched transactions."""
    require_finance_role(current_user)
    result = await apply_rules(db, current_user.company_id, on_date, current_user.id)
    return BankRulesApplyResponse(**result)

"""Analytic accounting API."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.analytic import AnalyticAccount, AnalyticAllocationRule, AnalyticEntry
from app.models.gl import GLAccount
from app.models.user import User
from app.schemas.analytic import AnalyticAccountCreate, AnalyticAccountResponse, AnalyticAccountUpdate, AnalyticAllocationRuleCreate, AnalyticAllocationRuleResponse, AnalyticEntryCreate, AnalyticEntryResponse, GLReconciliationItem
from app.schemas.common import ResponseBase
from app.services.accounting_periods import ensure_period_open

router = APIRouter(prefix="/analytic", tags=["ანალიტიკური აღრიცხვა"])

@router.get("/accounts", response_model=ResponseBase[list[AnalyticAccountResponse]])
async def list_accounts(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    accounts = (await db.execute(select(AnalyticAccount).where(AnalyticAccount.company_id == current_user.company_id).order_by(AnalyticAccount.code))).scalars().all()
    data=[]
    for a in accounts:
        totals=(await db.execute(select(
            func.coalesce(func.sum(case((AnalyticEntry.direction == "income", AnalyticEntry.amount), else_=0)),0),
            func.coalesce(func.sum(case((AnalyticEntry.direction == "expense", AnalyticEntry.amount), else_=0)),0),
        ).where(AnalyticEntry.analytic_account_id == a.id))).one()
        income, expense = float(totals[0]), float(totals[1])
        data.append(AnalyticAccountResponse(id=a.id, company_id=a.company_id, code=a.code, name=a.name, account_type=a.account_type, is_active=a.is_active, notes=a.notes, income_total=income, expense_total=expense, balance=income-expense, created_at=a.created_at))
    return ResponseBase(data=data)

@router.post("/accounts", response_model=ResponseBase[AnalyticAccountResponse], status_code=201)
async def create_account(payload: AnalyticAccountCreate, current_user: User = Depends(require_module("analytic", "can_create")), db: AsyncSession = Depends(get_db)):
    exists=await db.scalar(select(AnalyticAccount.id).where(AnalyticAccount.company_id==current_user.company_id, AnalyticAccount.code==payload.code))
    if exists: raise HTTPException(409, "ამ კოდით ანალიტიკური ანგარიში უკვე არსებობს")
    a=AnalyticAccount(company_id=current_user.company_id, **payload.model_dump()); db.add(a); await db.flush(); await db.refresh(a)
    return ResponseBase(data=AnalyticAccountResponse(id=a.id, company_id=a.company_id, code=a.code, name=a.name, account_type=a.account_type, is_active=a.is_active, notes=a.notes, created_at=a.created_at), message="ანალიტიკური ანგარიში შექმნილია")

@router.put("/accounts/{account_id}", response_model=ResponseBase)
async def update_account(account_id: UUID, payload: AnalyticAccountUpdate, current_user: User = Depends(require_module("analytic", "can_edit")), db: AsyncSession = Depends(get_db)):
    a=(await db.execute(select(AnalyticAccount).where(AnalyticAccount.id==account_id, AnalyticAccount.company_id==current_user.company_id))).scalar_one_or_none()
    if not a: raise HTTPException(404,"ანგარიში არ მოიძებნა")
    for k,v in payload.model_dump(exclude_unset=True).items(): setattr(a,k,v)
    return ResponseBase(message="ანგარიში განახლებულია")

@router.get("/entries", response_model=ResponseBase[list[AnalyticEntryResponse]])
async def list_entries(account_id: UUID | None = None, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q=select(AnalyticEntry).options(joinedload(AnalyticEntry.analytic_account)).where(AnalyticEntry.company_id==current_user.company_id)
    if account_id: q=q.where(AnalyticEntry.analytic_account_id==account_id)
    rows=(await db.execute(q.order_by(AnalyticEntry.entry_date.desc()))).unique().scalars().all()
    return ResponseBase(data=[AnalyticEntryResponse(id=e.id, analytic_account_id=e.analytic_account_id, analytic_account_name=e.analytic_account.name, gl_account_id=e.gl_account_id, entry_date=e.entry_date, description=e.description, amount=float(e.amount), direction=e.direction, reference=e.reference, created_at=e.created_at) for e in rows])

@router.post("/entries", response_model=ResponseBase[AnalyticEntryResponse], status_code=201)
async def create_entry(payload: AnalyticEntryCreate, current_user: User = Depends(require_module("analytic", "can_create")), db: AsyncSession = Depends(get_db)):
    await ensure_period_open(db, current_user.company_id, payload.entry_date)
    a=(await db.execute(select(AnalyticAccount).where(AnalyticAccount.id==payload.analytic_account_id, AnalyticAccount.company_id==current_user.company_id, AnalyticAccount.is_active.is_(True)))).scalar_one_or_none()
    if not a: raise HTTPException(404,"აქტიური ანალიტიკური ანგარიში არ მოიძებნა")
    if payload.gl_account_id is not None:
        gl_account = await db.scalar(select(GLAccount.id).where(
            GLAccount.id == payload.gl_account_id,
            GLAccount.company_id == current_user.company_id,
            GLAccount.is_active.is_(True),
        ))
        if not gl_account: raise HTTPException(404, "აქტიური GL ანგარიში არ მოიძებნა")
    e=AnalyticEntry(company_id=current_user.company_id, **payload.model_dump()); db.add(e); await db.flush(); await db.refresh(e)
    return ResponseBase(data=AnalyticEntryResponse(id=e.id, analytic_account_id=e.analytic_account_id, analytic_account_name=a.name, gl_account_id=e.gl_account_id, entry_date=e.entry_date, description=e.description, amount=float(e.amount), direction=e.direction, reference=e.reference, created_at=e.created_at), message="ანალიტიკური ჩანაწერი დამატებულია")

@router.delete("/entries/{entry_id}", response_model=ResponseBase)
async def delete_entry(entry_id: UUID, current_user: User = Depends(require_module("analytic", "can_edit")), db: AsyncSession = Depends(get_db)):
    e=(await db.execute(select(AnalyticEntry).where(AnalyticEntry.id==entry_id, AnalyticEntry.company_id==current_user.company_id))).scalar_one_or_none()
    if not e: raise HTTPException(404,"ჩანაწერი არ მოიძებნა")
    await ensure_period_open(db, current_user.company_id, e.entry_date)
    await db.delete(e); return ResponseBase(message="ჩანაწერი წაშლილია")


# ── Allocation Rules ─────────────────────────────────────────────────────────

@router.get("/allocation-rules", response_model=ResponseBase[list[AnalyticAllocationRuleResponse]])
async def list_allocation_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rules = (await db.execute(
        select(AnalyticAllocationRule)
        .where(AnalyticAllocationRule.company_id == current_user.company_id)
        .order_by(AnalyticAllocationRule.name)
    )).scalars().all()

    data = []
    for r in rules:
        source = await db.scalar(select(GLAccount).where(GLAccount.id == r.source_gl_account_id))
        target = await db.scalar(select(AnalyticAccount).where(AnalyticAccount.id == r.target_analytic_account_id))
        data.append(AnalyticAllocationRuleResponse(
            id=r.id, company_id=r.company_id, name=r.name,
            source_gl_account_id=r.source_gl_account_id,
            source_gl_account_code=source.code if source else "",
            source_gl_account_name=source.name if source else "",
            target_analytic_account_id=r.target_analytic_account_id,
            target_analytic_account_code=target.code if target else "",
            target_analytic_account_name=target.name if target else "",
            allocation_percent=float(r.allocation_percent),
            period=r.period, is_active=r.is_active, created_at=r.created_at,
        ))
    return ResponseBase(data=data)


@router.post("/allocation-rules", response_model=ResponseBase[AnalyticAllocationRuleResponse], status_code=201)
async def create_allocation_rule(
    payload: AnalyticAllocationRuleCreate,
    current_user: User = Depends(require_module("analytic", "can_create")),
    db: AsyncSession = Depends(get_db),
):
    rule = AnalyticAllocationRule(company_id=current_user.company_id, **payload.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    source = await db.scalar(select(GLAccount).where(GLAccount.id == rule.source_gl_account_id))
    target = await db.scalar(select(AnalyticAccount).where(AnalyticAccount.id == rule.target_analytic_account_id))
    return ResponseBase(data=AnalyticAllocationRuleResponse(
        id=rule.id, company_id=rule.company_id, name=rule.name,
        source_gl_account_id=rule.source_gl_account_id,
        source_gl_account_code=source.code if source else "",
        source_gl_account_name=source.name if source else "",
        target_analytic_account_id=rule.target_analytic_account_id,
        target_analytic_account_code=target.code if target else "",
        target_analytic_account_name=target.name if target else "",
        allocation_percent=float(rule.allocation_percent),
        period=rule.period, is_active=rule.is_active, created_at=rule.created_at,
    ), message="განაწილების წესი შექმნილია")


# ── GL Reconciliation ────────────────────────────────────────────────────────

@router.get("/gl-reconciliation", response_model=ResponseBase[list[GLReconciliationItem]])
async def gl_reconciliation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare GL account balances with analytic entry totals per GL account."""
    company_id = current_user.company_id

    # Get all GL accounts that have analytic entries
    gl_ids = (await db.execute(
        select(AnalyticEntry.gl_account_id).where(
            AnalyticEntry.company_id == company_id,
            AnalyticEntry.gl_account_id.isnot(None),
        ).distinct()
    )).scalars().all()

    result = []
    for gl_id in gl_ids:
        gl = await db.scalar(select(GLAccount).where(GLAccount.id == gl_id))
        if not gl:
            continue

        # GL balance
        from app.models.gl import JournalEntryLine, JournalEntry
        gl_bal = await db.scalar(
            select(func.coalesce(func.sum(JournalEntryLine.debit_amount - JournalEntryLine.credit_amount), 0))
            .select_from(JournalEntryLine)
            .join(JournalEntry)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntryLine.gl_account_id == gl_id,
            )
        )

        # Analytic total for this GL account
        analytic_total = await db.scalar(
            select(func.coalesce(func.sum(
                case((AnalyticEntry.direction == "income", AnalyticEntry.amount), else_=-AnalyticEntry.amount)
            ), 0))
            .where(
                AnalyticEntry.company_id == company_id,
                AnalyticEntry.gl_account_id == gl_id,
            )
        )

        gl_bal_f = float(gl_bal or 0)
        analytic_f = float(analytic_total or 0)
        result.append(GLReconciliationItem(
            gl_account_id=gl_id,
            gl_account_code=gl.code,
            gl_account_name=gl.name,
            gl_balance=gl_bal_f,
            analytic_balance=analytic_f,
            difference=round(gl_bal_f - analytic_f, 2),
        ))

    return ResponseBase(data=result)

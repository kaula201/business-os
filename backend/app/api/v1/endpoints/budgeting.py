"""Budgeting API: budget plans, lines, actual vs planned comparison."""
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.audit import AuditLog
from app.models.budgeting import BudgetLine, BudgetPlan
from app.models.gl import GLAccount, JournalEntryLine, JournalEntry
from app.models.user import User
from app.schemas.budgeting import (
    BudgetLineCreate,
    BudgetLineCreateBatch,
    BudgetLineResponse,
    BudgetPeriodSummary,
    BudgetPlanCreate,
    BudgetPlanResponse,
    BudgetPlanUpdate,
    BudgetScenarioResponse,
)
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/budgeting", tags=["ბიუჯეტირება"])


# ── Budget Plans ─────────────────────────────────────────────────────

@router.get("/plans", response_model=ResponseBase[list[BudgetPlanResponse]])
async def list_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BudgetPlan)
        .where(BudgetPlan.company_id == current_user.company_id)
        .order_by(BudgetPlan.fiscal_year.desc(), BudgetPlan.name)
    )
    plans = result.scalars().all()

    data = []
    for plan in plans:
        # Calculate totals
        total_planned = await db.scalar(
            select(sa_func.coalesce(sa_func.sum(BudgetLine.planned_amount), 0))
            .where(BudgetLine.plan_id == plan.id)
        )

        # Get actual amounts from GL
        gl_ids_result = await db.execute(
            select(BudgetLine.gl_account_id).where(BudgetLine.plan_id == plan.id).distinct()
        )
        gl_ids = [row[0] for row in gl_ids_result.fetchall()]

        total_actual = 0
        if gl_ids:
            actual_result = await db.execute(
                select(sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount - JournalEntryLine.credit_amount), 0))
                .select_from(JournalEntryLine)
                .join(JournalEntry)
                .where(
                    JournalEntry.company_id == current_user.company_id,
                    JournalEntryLine.gl_account_id.in_(gl_ids),
                    sa_func.extract("year", JournalEntry.entry_date) == plan.fiscal_year,
                )
            )
            total_actual = float(actual_result.scalar())

        data.append(BudgetPlanResponse(
            id=plan.id, company_id=plan.company_id, name=plan.name,
            fiscal_year=plan.fiscal_year, period_type=plan.period_type,
            status=plan.status, notes=plan.notes,
            total_planned=float(total_planned),
            total_actual=abs(total_actual),
            created_at=plan.created_at, updated_at=plan.updated_at,
        ))

    return ResponseBase(data=data)


@router.post("/plans", response_model=ResponseBase[BudgetPlanResponse], status_code=201)
async def create_plan(
    payload: BudgetPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = BudgetPlan(
        company_id=current_user.company_id,
        created_by=current_user.id,
        **payload.model_dump(),
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return ResponseBase(data=BudgetPlanResponse(
        id=plan.id, company_id=plan.company_id, name=plan.name,
        fiscal_year=plan.fiscal_year, period_type=plan.period_type,
        status=plan.status, notes=plan.notes,
        total_planned=0, total_actual=0,
        created_at=plan.created_at, updated_at=plan.updated_at,
    ), message="ბიუჯეტი შექმნილია")


@router.put("/plans/{plan_id}", response_model=ResponseBase[BudgetPlanResponse])
async def update_plan(
    plan_id: UUID,
    payload: BudgetPlanUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = (
        await db.execute(
            select(BudgetPlan).where(
                BudgetPlan.id == plan_id,
                BudgetPlan.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="ბიუჯეტი არ მოიძებნა")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)
    await db.flush()
    await db.refresh(plan)
    return ResponseBase(data=BudgetPlanResponse(
        id=plan.id, company_id=plan.company_id, name=plan.name,
        fiscal_year=plan.fiscal_year, period_type=plan.period_type,
        status=plan.status, notes=plan.notes,
        total_planned=0, total_actual=0,
        created_at=plan.created_at, updated_at=plan.updated_at,
    ), message="ბიუჯეტი განახლებულია")


@router.delete("/plans/{plan_id}", response_model=ResponseBase)
async def delete_plan(
    plan_id: UUID,
    current_user: User = Depends(require_module("budgeting", "can_edit")),
    db: AsyncSession = Depends(get_db),
):
    plan = (
        await db.execute(
            select(BudgetPlan).where(
                BudgetPlan.id == plan_id,
                BudgetPlan.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="ბიუჯეტი არ მოიძებნა")
    from app.api.v1.endpoints.purchase_orders import add_audit
    add_audit(db, current_user, "budget_plan.deleted", "budget_plan", plan.id, {
        "name": plan.name, "fiscal_year": plan.fiscal_year,
    })
    await db.delete(plan)
    return ResponseBase(message="ბიუჯეტი წაშლილია")


# ── Budget Lines ──────────────────────────────────────────────────────

@router.get("/plans/{plan_id}/lines", response_model=ResponseBase[list[BudgetLineResponse]])
async def list_budget_lines(
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = (
        await db.execute(
            select(BudgetPlan).where(
                BudgetPlan.id == plan_id,
                BudgetPlan.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="ბიუჯეტი არ მოიძებნა")

    result = await db.execute(
        select(BudgetLine)
        .options(joinedload(BudgetLine.gl_account))
        .where(BudgetLine.plan_id == plan_id)
        .order_by(BudgetLine.period, BudgetLine.gl_account_id)
    )
    lines = result.unique().scalars().all()

    data = []
    for line in lines:
        # Get actual amount from GL for this account + period
        actual_result = await db.execute(
            select(sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount - JournalEntryLine.credit_amount), 0))
            .select_from(JournalEntryLine)
            .join(JournalEntry)
            .where(
                JournalEntry.company_id == current_user.company_id,
                JournalEntryLine.gl_account_id == line.gl_account_id,
                sa_func.to_char(JournalEntry.entry_date, "YYYY-MM") == line.period,
            )
        )
        actual = float(actual_result.scalar())
        planned = float(line.planned_amount)
        variance = planned - abs(actual)
        variance_pct = round((variance / planned * 100), 1) if planned > 0 else None

        data.append(BudgetLineResponse(
            id=line.id, plan_id=line.plan_id,
            gl_account_id=line.gl_account_id,
            gl_account_code=line.gl_account.code,
            gl_account_name=line.gl_account.name,
            period=line.period,
            planned_amount=planned,
            actual_amount=abs(actual),
            variance=round(variance, 2),
            variance_percent=variance_pct,
            notes=line.notes,
            created_at=line.created_at,
        ))

    return ResponseBase(data=data)


@router.post("/plans/{plan_id}/lines", response_model=ResponseBase[list[BudgetLineResponse]], status_code=201)
async def create_budget_lines(
    plan_id: UUID,
    payload: BudgetLineCreateBatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = (
        await db.execute(
            select(BudgetPlan).where(
                BudgetPlan.id == plan_id,
                BudgetPlan.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="ბიუჯეტი არ მოიძებნა")

    created = []
    for line_data in payload.lines:
        line = BudgetLine(
            company_id=current_user.company_id,
            plan_id=plan_id,
            **line_data.model_dump(),
        )
        db.add(line)
        created.append(line)

    await db.flush()

    # Re-fetch with joins
    data = []
    for line in created:
        result = await db.execute(
            select(BudgetLine)
            .options(joinedload(BudgetLine.gl_account))
            .where(BudgetLine.id == line.id)
        )
        l = result.unique().scalar_one()
        data.append(BudgetLineResponse(
            id=l.id, plan_id=l.plan_id,
            gl_account_id=l.gl_account_id,
            gl_account_code=l.gl_account.code,
            gl_account_name=l.gl_account.name,
            period=l.period,
            planned_amount=float(l.planned_amount),
            actual_amount=0,
            variance=float(l.planned_amount),
            variance_percent=None,
            notes=l.notes,
            created_at=l.created_at,
        ))

    return ResponseBase(data=data, message="ბიუჯეტის ხაზები დამატებულია")


# ── Enhanced: Period Breakdown ────────────────────────────────────────────────

@router.get("/plans/{plan_id}/period-breakdown", response_model=ResponseBase[list[BudgetPeriodSummary]])
async def budget_period_breakdown(
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return per-period breakdown for a budget plan."""
    plan = (
        await db.execute(
            select(BudgetPlan).where(
                BudgetPlan.id == plan_id,
                BudgetPlan.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="ბიუჯეტი არ მოიძებნა")

    lines = (await db.execute(
        select(BudgetLine).where(BudgetLine.plan_id == plan_id)
    )).scalars().all()

    periods = {}
    for line in lines:
        if line.period not in periods:
            periods[line.period] = {"planned": 0.0, "actual": 0.0}
        periods[line.period]["planned"] += float(line.planned_amount)

        # Get actual from GL
        actual = await db.scalar(
            select(sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount - JournalEntryLine.credit_amount), 0))
            .select_from(JournalEntryLine)
            .join(JournalEntry)
            .where(
                JournalEntry.company_id == current_user.company_id,
                JournalEntryLine.gl_account_id == line.gl_account_id,
                sa_func.to_char(JournalEntry.entry_date, "YYYY-MM") == line.period,
            )
        )
        periods[line.period]["actual"] += abs(float(actual))

    result = []
    for period in sorted(periods.keys()):
        p = periods[period]
        variance = p["planned"] - p["actual"]
        vpct = round((variance / p["planned"] * 100), 1) if p["planned"] > 0 else None
        result.append(BudgetPeriodSummary(
            period=period, planned=p["planned"], actual=p["actual"],
            variance=round(variance, 2), variance_percent=vpct,
        ))

    return ResponseBase(data=result)


# ── Enhanced: Scenario Comparison ─────────────────────────────────────────────

@router.get("/scenarios", response_model=ResponseBase[list[BudgetScenarioResponse]])
async def list_scenarios(
    fiscal_year: int | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all budget scenarios for comparison."""
    query = select(BudgetPlan).where(BudgetPlan.company_id == current_user.company_id)
    if fiscal_year:
        query = query.where(BudgetPlan.fiscal_year == fiscal_year)
    plans = (await db.execute(query.order_by(BudgetPlan.fiscal_year.desc(), BudgetPlan.scenario))).scalars().all()

    result = []
    for plan in plans:
        total_planned = await db.scalar(
            select(sa_func.coalesce(sa_func.sum(BudgetLine.planned_amount), 0))
            .where(BudgetLine.plan_id == plan.id)
        )
        gl_ids = [r[0] for r in (await db.execute(
            select(BudgetLine.gl_account_id).where(BudgetLine.plan_id == plan.id).distinct()
        )).fetchall()]
        total_actual = 0
        if gl_ids:
            actual = await db.scalar(
                select(sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount - JournalEntryLine.credit_amount), 0))
                .select_from(JournalEntryLine).join(JournalEntry)
                .where(JournalEntry.company_id == current_user.company_id, JournalEntryLine.gl_account_id.in_(gl_ids))
            )
            total_actual = abs(float(actual))

        result.append(BudgetScenarioResponse(
            id=plan.id, name=plan.name, scenario=plan.scenario,
            fiscal_year=plan.fiscal_year, total_planned=float(total_planned),
            total_actual=total_actual, status=plan.status,
        ))

    return ResponseBase(data=result)

"""Odoo-depth payroll engine endpoints — structures, rules, parameters, work entries."""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.hr import PayrollEntry
from app.models.payroll_engine import (
    PayrollAdjustment,
    PayrollLine,
    RuleParameter,
    SalaryRule,
    SalaryStructure,
    WorkEntry,
)
from app.models.user import User
from app.schemas.common import ResponseBase
from app.services.payroll_engine import compute_payroll_with_rules, get_rule_parameters

router = APIRouter(prefix="/payroll-engine", tags=["პეიროლი — ძრავა"])


def require_hr_admin(user: User) -> None:
    if user.role not in (User.Role.ADMIN, User.Role.ACCOUNTANT):
        raise HTTPException(status_code=403, detail="ოპერაცია ხელმისაწვდომია მხოლოდ ადმინის/ბუღალტერისთვის")


# ── Salary structures ─────────────────────────────────────────────────────────

@router.get("/structures", response_model=ResponseBase[list[dict]])
async def list_structures(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(select(SalaryStructure).where(
        SalaryStructure.company_id == current_user.company_id,
    ).order_by(SalaryStructure.created_at))).scalars().all()
    return ResponseBase(data=[{
        "id": str(s.id), "name": s.name, "description": s.description, "is_active": s.is_active,
    } for s in rows])


@router.post("/structures", response_model=ResponseBase[dict], status_code=201)
async def create_structure(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_hr_admin(current_user)
    s = SalaryStructure(
        company_id=current_user.company_id,
        name=data.get("name", ""),
        description=data.get("description"),
        is_active=bool(data.get("is_active", True)),
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return ResponseBase(data={"id": str(s.id), "name": s.name}, message="სტრუქტურა შეიქმნა")


@router.delete("/structures/{structure_id}", response_model=ResponseBase[dict])
async def delete_structure(
    structure_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_hr_admin(current_user)
    s = (await db.execute(select(SalaryStructure).where(
        SalaryStructure.id == structure_id, SalaryStructure.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="სტრუქტურა არ მოიძებნა")
    await db.delete(s)
    await db.commit()
    return ResponseBase(data={"id": str(structure_id)}, message="სტრუქტურა წაიშალა")


# ── Salary rules ──────────────────────────────────────────────────────────────

@router.get("/structures/{structure_id}/rules", response_model=ResponseBase[list[dict]])
async def list_rules(
    structure_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(select(SalaryRule).where(
        SalaryRule.structure_id == structure_id,
        SalaryRule.company_id == current_user.company_id,
    ).order_by(SalaryRule.sequence))).scalars().all()
    return ResponseBase(data=[{
        "id": str(r.id), "code": r.code, "name": r.name, "category": r.category,
        "amount_type": r.amount_type, "amount": float(r.amount), "formula": r.formula,
        "basis": r.basis, "sequence": r.sequence, "is_active": r.is_active,
    } for r in rows])


@router.post("/structures/{structure_id}/rules", response_model=ResponseBase[dict], status_code=201)
async def create_rule(
    structure_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_hr_admin(current_user)
    r = SalaryRule(
        company_id=current_user.company_id,
        structure_id=structure_id,
        code=data.get("code", ""),
        name=data.get("name", ""),
        category=data.get("category", "addition"),
        amount_type=data.get("amount_type", "fixed"),
        amount=Decimal(str(data.get("amount", 0))),
        formula=data.get("formula"),
        basis=data.get("basis", "gross"),
        sequence=int(data.get("sequence", 10)),
        is_active=bool(data.get("is_active", True)),
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return ResponseBase(data={"id": str(r.id), "code": r.code}, message="წესი შეიქმნა")


@router.delete("/rules/{rule_id}", response_model=ResponseBase[dict])
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_hr_admin(current_user)
    r = (await db.execute(select(SalaryRule).where(
        SalaryRule.id == rule_id, SalaryRule.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="წესი არ მოიძებნა")
    await db.delete(r)
    await db.commit()
    return ResponseBase(data={"id": str(rule_id)}, message="წესი წაიშალა")


# ── Rule parameters ───────────────────────────────────────────────────────────

@router.get("/parameters", response_model=ResponseBase[dict])
async def list_parameters(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    params = await get_rule_parameters(db, current_user.company_id)
    return ResponseBase(data=params)


@router.post("/parameters", response_model=ResponseBase[dict], status_code=201)
async def set_parameter(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_hr_admin(current_user)
    key = data.get("key", "")
    if not key:
        raise HTTPException(status_code=422, detail="key სავალდებულოა")
    existing = (await db.execute(select(RuleParameter).where(
        RuleParameter.company_id == current_user.company_id,
        RuleParameter.key == key,
    ))).scalar_one_or_none()
    if existing:
        existing.value = Decimal(str(data.get("value", 0)))
    else:
        db.add(RuleParameter(
            company_id=current_user.company_id,
            key=key,
            value=Decimal(str(data.get("value", 0))),
            description=data.get("description"),
        ))
    await db.commit()
    return ResponseBase(data={"key": key}, message="პარამეტრი შეინახა")


# ── Work entries ──────────────────────────────────────────────────────────────

@router.post("/work-entries", response_model=ResponseBase[dict], status_code=201)
async def create_work_entry(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_hr_admin(current_user)
    w = WorkEntry(
        company_id=current_user.company_id,
        employee_id=uuid.UUID(str(data.get("employee_id"))),
        period_year=int(data.get("period_year")),
        period_month=int(data.get("period_month")),
        worked_days=Decimal(str(data.get("worked_days", 0))),
        worked_hours=Decimal(str(data.get("worked_hours", 0))),
        overtime_hours=Decimal(str(data.get("overtime_hours", 0))),
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return ResponseBase(data={"id": str(w.id)}, message="სამუშაო ჩანაწერი შეიქმნა")


@router.get("/work-entries", response_model=ResponseBase[list[dict]])
async def list_work_entries(
    employee_id: uuid.UUID | None = None,
    period_year: int | None = None,
    period_month: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(WorkEntry).where(WorkEntry.company_id == current_user.company_id)
    if employee_id:
        query = query.where(WorkEntry.employee_id == employee_id)
    if period_year:
        query = query.where(WorkEntry.period_year == period_year)
    if period_month:
        query = query.where(WorkEntry.period_month == period_month)
    rows = (await db.execute(query.order_by(WorkEntry.period_year.desc(), WorkEntry.period_month.desc()))).scalars().all()
    return ResponseBase(data=[{
        "id": str(w.id), "employee_id": str(w.employee_id),
        "period_year": w.period_year, "period_month": w.period_month,
        "worked_days": float(w.worked_days), "worked_hours": float(w.worked_hours),
        "overtime_hours": float(w.overtime_hours),
    } for w in rows])


# ── Bonuses / deductions (Odoo payslip.input) ────────────────────────────────

@router.get("/adjustments", response_model=ResponseBase[list[dict]])
async def list_adjustments(
    employee_id: uuid.UUID | None = None,
    period_year: int | None = None,
    period_month: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(PayrollAdjustment).where(PayrollAdjustment.company_id == current_user.company_id)
    if employee_id:
        query = query.where(PayrollAdjustment.employee_id == employee_id)
    if period_year:
        query = query.where(PayrollAdjustment.period_year == period_year)
    if period_month:
        query = query.where(PayrollAdjustment.period_month == period_month)
    rows = (await db.execute(query.order_by(PayrollAdjustment.created_at.desc()))).scalars().all()
    return ResponseBase(data=[{
        "id": str(a.id), "employee_id": str(a.employee_id),
        "period_year": a.period_year, "period_month": a.period_month,
        "kind": a.kind, "amount": float(a.amount), "reason": a.reason,
    } for a in rows])


@router.post("/adjustments", response_model=ResponseBase[dict], status_code=201)
async def create_adjustment(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_hr_admin(current_user)
    a = PayrollAdjustment(
        company_id=current_user.company_id,
        employee_id=uuid.UUID(str(data.get("employee_id"))),
        period_year=int(data.get("period_year")),
        period_month=int(data.get("period_month")),
        kind=data.get("kind", "bonus"),
        amount=Decimal(str(data.get("amount", 0))),
        reason=data.get("reason"),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return ResponseBase(data={"id": str(a.id), "kind": a.kind}, message="ბონუსი/დაქვითვა შეინახა")


@router.delete("/adjustments/{adjustment_id}", response_model=ResponseBase[dict])
async def delete_adjustment(
    adjustment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_hr_admin(current_user)
    a = (await db.execute(select(PayrollAdjustment).where(
        PayrollAdjustment.id == adjustment_id,
        PayrollAdjustment.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="ჩანაწერი არ მოიძებნა")
    await db.delete(a)
    await db.commit()
    return ResponseBase(data={"id": str(adjustment_id)}, message="ჩანაწერი წაიშალა")


# ── Engine: calculate with rules ──────────────────────────────────────────────

@router.post("/calculate", response_model=ResponseBase[dict])
async def calculate_with_rules(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the salary structure rules for one employee and persist lines."""
    require_hr_admin(current_user)
    employee_id = uuid.UUID(str(data.get("employee_id")))
    year = int(data.get("period_year"))
    month = int(data.get("period_month"))
    base_salary = Decimal(str(data.get("base_salary", 0)))
    structure_id = uuid.UUID(str(data["structure_id"])) if data.get("structure_id") else None

    result = await compute_payroll_with_rules(
        db, current_user.company_id, employee_id, base_salary,
        year, month,
        pension_participant=bool(data.get("pension_participant", True)),
        additions=Decimal(str(data.get("additions", 0))),
        deductions=Decimal(str(data.get("deductions", 0))),
        structure_id=structure_id,
    )

    # persist payroll entry + lines (upsert: recalculate updates the same period entry)
    existing = (await db.execute(select(PayrollEntry).where(
        PayrollEntry.company_id == current_user.company_id,
        PayrollEntry.employee_id == employee_id,
        PayrollEntry.period_year == year,
        PayrollEntry.period_month == month,
    ))).scalar_one_or_none()

    if existing:
        entry = existing
        entry.base_salary = base_salary
        entry.gross_pay = Decimal(str(result["gross_pay"]))
        entry.additions = Decimal(str(result["additions"]))
        entry.deductions = Decimal(str(result["deductions"]))
        entry.pension_contribution = Decimal(str(result["pension_contribution"]))
        entry.income_tax = Decimal(str(result["income_tax"]))
        entry.net_pay = Decimal(str(result["net_pay"]))
        entry.status = PayrollEntry.Status.DRAFT
        # drop previous lines, recompute
        old_lines = (await db.execute(select(PayrollLine).where(
            PayrollLine.payroll_entry_id == entry.id,
        ))).scalars().all()
        for ol in old_lines:
            await db.delete(ol)
        await db.flush()
    else:
        entry = PayrollEntry(
            company_id=current_user.company_id,
            employee_id=employee_id,
            period_year=year,
            period_month=month,
            base_salary=base_salary,
            gross_pay=Decimal(str(result["gross_pay"])),
            additions=Decimal(str(result["additions"])),
            deductions=Decimal(str(result["deductions"])),
            pension_contribution=Decimal(str(result["pension_contribution"])),
            income_tax=Decimal(str(result["income_tax"])),
            net_pay=Decimal(str(result["net_pay"])),
            status=PayrollEntry.Status.DRAFT,
        )
        db.add(entry)
        await db.flush()

    for line in result["lines"]:
        db.add(PayrollLine(
            company_id=current_user.company_id,
            payroll_entry_id=entry.id,
            code=line["code"],
            name=line["name"],
            category=line["category"],
            amount=Decimal(str(line["amount"])),
            basis_amount=Decimal(str(line["basis_amount"])),
            formula_used=line["formula_used"],
        ))
    await db.commit()

    return ResponseBase(data={
        "entry_id": str(entry.id),
        **result,
    }, message="გაანგარიშება დასრულდა — წესები შესრულდა")


@router.get("/entries/{entry_id}/lines", response_model=ResponseBase[list[dict]])
async def entry_lines(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(select(PayrollLine).where(
        PayrollLine.payroll_entry_id == entry_id,
        PayrollLine.company_id == current_user.company_id,
    ))).scalars().all()
    return ResponseBase(data=[{
        "id": str(l.id), "code": l.code, "name": l.name, "category": l.category,
        "amount": float(l.amount), "basis_amount": float(l.basis_amount),
        "formula_used": l.formula_used,
    } for l in rows])

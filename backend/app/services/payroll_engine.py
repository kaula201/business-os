"""Odoo-depth payroll calculation engine.

Salary rules are evaluated in sequence against a safe namespace:
  gross, base_salary, additions, deductions, pension_participant,
  worked_days, worked_hours, period_year, period_month, params (dict)

amount_type:
  fixed      → amount
  percentage → basis * amount / 100
  formula    → safe-eval of `formula` (no builtins, no imports)

Categories accumulate: addition → gross additions; deduction → deductions;
tax/pension → withheld; net → final net pay.
"""
from __future__ import annotations

import ast
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll_engine import RuleParameter, SalaryRule, SalaryStructure, WorkEntry

# Georgian legal defaults (overridable via rule_parameters)
DEFAULT_PARAMS = {
    "income_tax_rate_2025_plus": 0.15,   # Tax Code Art. 81 — reduced flat rate from 2025-01-01
    "income_tax_rate_legacy": 0.20,      # general rate before 2025-01-01
    "pension_employee_rate": 0.02,       # Pension Law Art. 37
    "pension_ceiling": 200000.0,
    "overtime_rate": 1.5,
}


def _safe_eval(expr: str, namespace: dict) -> float:
    """Evaluate a restricted Python expression — no builtins, no attributes."""
    tree = ast.parse(expr, mode="eval")
    allowed = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.USub,
               ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
               ast.BoolOp, ast.And, ast.Or, ast.IfExp, ast.Call, ast.Load,
               ast.Subscript, ast.Index}
    for node in ast.walk(tree):
        if type(node) not in allowed:
            raise ValueError(f"აკრძალული გამოთქმა: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in {"min", "max", "round", "abs"}:
                raise ValueError("მხოლოდ min/max/round/abs ფუნქციებია დაშვებული")
        if isinstance(node, ast.Subscript):
            # only params["key"] access is allowed
            if not (isinstance(node.value, ast.Name) and node.value.id == "params"):
                raise ValueError("მხოლოდ params-ზე წვდომაა დაშვებული")
    safe_ns = {k: v for k, v in namespace.items() if k in {
        "gross", "base_salary", "additions", "deductions", "pension_participant",
        "worked_days", "worked_hours", "overtime_hours", "period_year", "period_month",
        "params",
    }}
    safe_ns.update({"min": min, "max": max, "round": round, "abs": abs})
    return float(eval(compile(tree, "<rule>", "eval"), {"__builtins__": {}}, safe_ns))


async def get_rule_parameters(db: AsyncSession, company_id, **period) -> dict:
    """Load company rule parameters merged over Georgian legal defaults.

    `income_tax_rate` is period-aware: the reduced 15% flat rate applies to
    employment income from 2025-01-01 (Tax Code Art. 81 transitional
    provision); earlier periods use the general 20% rate. This matches
    payroll_rules.income_tax_rate_for() so all payroll paths agree.
    """
    from datetime import date as _date

    params = dict(DEFAULT_PARAMS)
    rows = (await db.execute(
        select(RuleParameter).where(RuleParameter.company_id == company_id)
    )).scalars().all()
    for r in rows:
        params[r.key] = float(r.value)

    year = period.get("period_year")
    month = period.get("period_month")
    if year and month and "income_tax_rate" not in params:
        period_date = _date(year, month, 1)
        # reduced rate from 2025-01-01 (matches payroll_rules income_tax_rate_for)
        if period_date >= _date(2025, 1, 1):
            params["income_tax_rate"] = params["income_tax_rate_2025_plus"]
        else:
            params["income_tax_rate"] = params["income_tax_rate_legacy"]
    return params


async def get_work_entry(db: AsyncSession, company_id, employee_id, year, month) -> dict:
    """Worked days/hours for the period (from work_entries or attendance)."""
    entry = (await db.execute(
        select(WorkEntry).where(
            WorkEntry.company_id == company_id,
            WorkEntry.employee_id == employee_id,
            WorkEntry.period_year == year,
            WorkEntry.period_month == month,
        )
    )).scalar_one_or_none()
    if entry:
        return {
            "worked_days": float(entry.worked_days),
            "worked_hours": float(entry.worked_hours),
            "overtime_hours": float(entry.overtime_hours),
        }
    # fallback: count attendance records for the period
    from app.models.hr import Attendance
    from datetime import date
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    rows = (await db.execute(
        select(Attendance).where(
            Attendance.company_id == company_id,
            Attendance.employee_id == employee_id,
            Attendance.date >= start,
            Attendance.date < end,
        )
    )).scalars().all()
    days = len(rows)
    hours = sum(float(r.hours_worked or 0) for r in rows)
    return {"worked_days": days, "worked_hours": hours, "overtime_hours": 0.0}


async def get_adjustments(db: AsyncSession, company_id, employee_id, year, month) -> dict:
    """Bonuses/deductions for the period — auto-included in calculation."""
    from app.models.payroll_engine import PayrollAdjustment
    rows = (await db.execute(
        select(PayrollAdjustment).where(
            PayrollAdjustment.company_id == company_id,
            PayrollAdjustment.employee_id == employee_id,
            PayrollAdjustment.period_year == year,
            PayrollAdjustment.period_month == month,
        )
    )).scalars().all()
    additions = Decimal("0")
    deductions = Decimal("0")
    items = []
    for a in rows:
        amt = a.amount
        if a.kind in ("bonus", "premium", "other"):
            additions += amt
        else:  # fine, advance
            deductions += amt
        items.append({
            "id": str(a.id), "kind": a.kind, "amount": float(amt), "reason": a.reason,
        })
    return {"additions": additions, "deductions": deductions, "items": items}


async def compute_payroll_with_rules(
    db: AsyncSession,
    company_id,
    employee_id,
    base_salary: Decimal,
    period_year: int,
    period_month: int,
    pension_participant: bool = True,
    additions: Decimal = Decimal("0"),
    deductions: Decimal = Decimal("0"),
    structure_id=None,
) -> dict:
    """Run the salary structure rules and return lines + totals."""
    params = await get_rule_parameters(db, company_id, period_year=period_year, period_month=period_month)
    work = await get_work_entry(db, company_id, employee_id, period_year, period_month)
    adj = await get_adjustments(db, company_id, employee_id, period_year, period_month)
    additions = additions + adj["additions"]
    deductions = deductions + adj["deductions"]

    # resolve structure: explicit or first active
    if structure_id is None:
        struct = (await db.execute(
            select(SalaryStructure).where(
                SalaryStructure.company_id == company_id,
                SalaryStructure.is_active.is_(True),
            ).order_by(SalaryStructure.created_at).limit(1)
        )).scalar_one_or_none()
        structure_id = struct.id if struct else None

    rules = []
    if structure_id:
        rules = (await db.execute(
            select(SalaryRule).where(
                SalaryRule.structure_id == structure_id,
                SalaryRule.company_id == company_id,
                SalaryRule.is_active.is_(True),
            ).order_by(SalaryRule.sequence, SalaryRule.created_at)
        )).scalars().all()

    gross = float(base_salary)
    lines = []
    total_additions = float(additions)
    total_deductions = float(deductions)
    total_tax = 0.0
    total_pension = 0.0

    ns = {
        "gross": gross, "base_salary": float(base_salary),
        "additions": float(additions), "deductions": float(deductions),
        "pension_participant": pension_participant,
        "worked_days": work["worked_days"], "worked_hours": work["worked_hours"],
        "overtime_hours": work["overtime_hours"],
        "period_year": period_year, "period_month": period_month,
        "params": params,
    }

    for rule in rules:
        try:
            if rule.amount_type == "fixed":
                amount = float(rule.amount)
                basis = 0.0
            elif rule.amount_type == "percentage":
                basis = ns.get(rule.basis, gross)
                amount = basis * float(rule.amount) / 100.0
            else:  # formula
                basis = ns.get(rule.basis, gross)
                ns["gross"] = gross
                amount = _safe_eval(rule.formula or "0", ns)
            amount = round(amount, 2)
        except Exception:
            continue

        lines.append({
            "code": rule.code, "name": rule.name, "category": rule.category,
            "amount": amount, "basis_amount": round(basis, 2),
            "formula_used": rule.formula if rule.amount_type == "formula" else rule.amount_type,
        })

        if rule.category == "addition":
            total_additions += amount
        elif rule.category == "deduction":
            total_deductions += amount
        elif rule.category == "tax":
            total_tax += amount
        elif rule.category == "pension":
            total_pension += amount

    gross_total = float(base_salary) + total_additions
    net = gross_total - total_deductions - total_tax - total_pension

    return {
        "lines": lines,
        "gross_pay": round(gross_total, 2),
        "additions": round(total_additions, 2),
        "deductions": round(total_deductions, 2),
        "pension_contribution": round(total_pension, 2),
        "income_tax": round(total_tax, 2),
        "net_pay": round(net, 2),
        "worked_days": work["worked_days"],
        "worked_hours": work["worked_hours"],
        "overtime_hours": work["overtime_hours"],
        "adjustments": adj["items"],
        "structure_id": str(structure_id) if structure_id else None,
        "params": params,
    }

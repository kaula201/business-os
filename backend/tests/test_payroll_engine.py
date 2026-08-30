"""Odoo-depth payroll engine tests — structures, rules, parameters, work entries."""
from datetime import date

import pytest
from httpx import AsyncClient

from app.models.hr import Employee, PayrollEntry
from app.models.payroll_engine import PayrollLine, RuleParameter, SalaryRule, SalaryStructure, WorkEntry
from app.services.payroll_engine import _safe_eval, compute_payroll_with_rules


@pytest.fixture
async def payroll_employee(test_company, db_session):
    """Employee in the shared test company."""
    emp = Employee(
        company_id=test_company.id, full_name="გიორგი თესტი",
        personal_number="01001001001", position="დეველოპერი",
        email="g@test.ge", hire_date=date(2024, 1, 1), base_salary=2000,
    )
    db_session.add(emp)
    await db_session.commit()
    await db_session.refresh(emp)
    return emp


async def test_safe_eval_rejects_imports_and_attributes():
    with pytest.raises(ValueError):
        _safe_eval("__import__('os').system('id')", {"gross": 1})
    with pytest.raises(ValueError):
        _safe_eval("gross.__class__", {"gross": 1})
    with pytest.raises(ValueError):
        _safe_eval("open('/etc/passwd')", {"gross": 1})


async def test_safe_eval_allows_params_and_math():
    ns = {"gross": 2000.0, "pension_participant": True,
          "params": {"income_tax_rate": 0.15, "pension_ceiling": 200000.0}}
    assert _safe_eval("round(gross * params['income_tax_rate'], 2)", ns) == 300.0
    assert _safe_eval("min(gross, 1000)", ns) == 1000.0
    assert _safe_eval("max(gross, 5000)", ns) == 5000.0


async def test_full_rule_flow(db_session, test_company, payroll_employee):
    """Structure + rules + params → calculate → Georgian taxes."""
    struct = SalaryStructure(company_id=test_company.id, name="სტანდარტული", is_active=True)
    db_session.add(struct)
    await db_session.flush()

    db_session.add(SalaryRule(
        company_id=test_company.id, structure_id=struct.id, code="PENSION", name="საპენსიო 2%",
        category="pension", amount_type="percentage", amount=2, basis="gross", sequence=10,
    ))
    db_session.add(SalaryRule(
        company_id=test_company.id, structure_id=struct.id, code="INCOME_TAX", name="საშემოსავლო 15%",
        category="tax", amount_type="formula",
        formula="round(gross * params['income_tax_rate'], 2)", basis="gross", sequence=20,
    ))
    db_session.add(RuleParameter(company_id=test_company.id, key="income_tax_rate", value=0.15))
    await db_session.commit()

    result = await compute_payroll_with_rules(
        db_session, test_company.id, payroll_employee.id, 2000, 2026, 8, structure_id=struct.id,
    )
    assert result["pension_contribution"] == 40.0
    assert result["income_tax"] == 300.0
    assert result["net_pay"] == 1660.0
    assert len(result["lines"]) == 2


async def test_work_entry_drives_proration(db_session, test_company, payroll_employee):
    """Work entry hours are exposed to formulas."""
    db_session.add(WorkEntry(
        company_id=test_company.id, employee_id=payroll_employee.id, period_year=2026, period_month=8,
        worked_days=21, worked_hours=168, overtime_hours=4,
    ))
    await db_session.commit()
    work = await compute_payroll_with_rules(db_session, test_company.id, payroll_employee.id, 2000, 2026, 8)
    assert work["worked_days"] == 21
    assert work["worked_hours"] == 168
    assert work["overtime_hours"] == 4


async def test_calculate_endpoint_upserts(client, auth_headers, test_company, payroll_employee, db_session):
    """POST /payroll-engine/calculate creates entry + lines; recalc updates same period."""
    struct = SalaryStructure(company_id=test_company.id, name="სტრუქტურა", is_active=True)
    db_session.add(struct)
    await db_session.flush()
    db_session.add(SalaryRule(
        company_id=test_company.id, structure_id=struct.id, code="PENSION", name="პენსია",
        category="pension", amount_type="percentage", amount=2, basis="gross", sequence=10,
    ))
    await db_session.commit()
    await db_session.refresh(struct)

    payload = {
        "employee_id": str(payroll_employee.id), "period_year": 2026, "period_month": 8,
        "base_salary": 2000, "structure_id": str(struct.id),
    }
    r1 = await client.post("/api/v1/payroll-engine/calculate", json=payload, headers=auth_headers)
    assert r1.status_code == 200, r1.text
    entry_id = r1.json()["data"]["entry_id"]

    r2 = await client.post("/api/v1/payroll-engine/calculate", json=payload, headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["data"]["entry_id"] == entry_id  # same entry, updated

    from sqlalchemy import select
    lines = (await db_session.execute(select(PayrollLine).where(PayrollLine.payroll_entry_id == entry_id))).scalars().all()
    assert len(lines) == 1
    assert lines[0].code == "PENSION"

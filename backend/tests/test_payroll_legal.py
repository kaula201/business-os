"""Payroll legal compliance — Georgia: 15% income tax, 2% pension, net = gross - tax - pension."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.hr import PayrollEntry
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_employee(client, auth_headers, salary: float) -> str:
    resp = await client.post("/api/v1/hr/employees", json={
        "full_name": f"Emp {salary}", "email": f"emp{int(salary)}@demo.ge",
        "base_salary": salary, "hire_date": "2026-01-01",
        "personal_number": f"0100000{int(salary)}", "position": "Tester",
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def test_payroll_15_percent_income_tax(client, auth_headers, test_company, db_session):
    """Georgia legal: 1000 GEL gross → 150 GEL tax (15%), 20 GEL pension (2%), net 830."""
    emp_id = await _make_employee(client, auth_headers, 1000)

    resp = await client.post("/api/v1/hr/payroll/calculate", json={
        "year": 2026, "month": 8, "employee_ids": [emp_id],
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text

    async with TestSessionLocal() as s:
        entry = (await s.execute(select(PayrollEntry).where(PayrollEntry.employee_id == emp_id))).scalar_one()
        assert entry.gross_pay == Decimal("1000.00")
        assert entry.income_tax == Decimal("150.00")  # 15% — legal requirement
        assert entry.pension_contribution == Decimal("20.00")  # 2%
        assert entry.net_pay == Decimal("830.00")  # 1000 - 150 - 20


async def test_payroll_15_percent_rounding(client, auth_headers, test_company, db_session):
    """3333.33 GEL → tax 499.9995 → 500.00 (rounded to 0.01)."""
    emp_id = await _make_employee(client, auth_headers, 3333.33)

    resp = await client.post("/api/v1/hr/payroll/calculate", json={
        "year": 2026, "month": 8, "employee_ids": [emp_id],
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text

    async with TestSessionLocal() as s:
        entry = (await s.execute(select(PayrollEntry).where(PayrollEntry.employee_id == emp_id))).scalar_one()
        assert entry.income_tax == Decimal("500.00")  # 3333.33 * 0.15 = 499.9995 → 500.00
        assert entry.net_pay == Decimal("3333.33") - Decimal("500.00") - Decimal("66.67")  # pension 66.6666 → 66.67

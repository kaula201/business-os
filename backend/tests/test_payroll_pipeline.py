"""P1-5: Payroll — calculate → payslip → GL posting (5200/2210/2220/2300)."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.gl import GLAccount, JournalEntryLine
from app.models.hr import Employee
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_payroll_payslip_gl(client, auth_headers, test_company):
    async with TestSessionLocal() as session:
        emp = Employee(
            company_id=test_company.id,
            personal_number="01001001002",
            full_name="Payroll GL Test",
            position="Accountant",
            hire_date=date(2026, 1, 1),
            status=Employee.Status.ACTIVE,
            base_salary=Decimal("1000.00"),
            salary_currency="GEL",
        )
        session.add(emp)
        await session.commit()
        emp_id = str(emp.id)

    # 1. Calculate payroll (15% tax, 2% pension)
    calc = await client.post("/api/v1/hr/payroll/calculate", json={
        "year": 2026, "month": 8, "employee_ids": [emp_id],
    }, headers=auth_headers)
    assert calc.status_code in (200, 201), calc.text

    # 2. Generate payslip → GL posting
    gen = await client.post("/api/v1/hr/payslips/generate", params={"year": 2026, "month": 8}, headers=auth_headers)
    assert gen.status_code == 201, gen.text
    assert len(gen.json()["data"]) == 1

    # 3. GL verification: 5200=1000, 2210=20, 2220=150, 2300=830
    async with TestSessionLocal() as s:
        accounts = (await s.execute(select(GLAccount).where(GLAccount.company_id == test_company.id))).scalars().all()
        acc = {a.code: a for a in accounts}
        balances = {}
        for code, a in acc.items():
            row = (await s.execute(
                select(
                    func.coalesce(func.sum(JournalEntryLine.debit_amount), 0),
                    func.coalesce(func.sum(JournalEntryLine.credit_amount), 0),
                ).where(JournalEntryLine.gl_account_id == a.id)
            )).one()
            dr, cr = Decimal(row[0]), Decimal(row[1])
            balances[code] = dr - cr if a.account_type in ("asset", "expense") else cr - dr

        assert balances.get("5200", Decimal("0")) == Decimal("1000.00"), f"5200={balances.get('5200')}"
        assert balances.get("2210", Decimal("0")) == Decimal("20.00"), f"2210={balances.get('2210')}"
        assert balances.get("2220", Decimal("0")) == Decimal("150.00"), f"2220={balances.get('2220')}"
        assert balances.get("2300", Decimal("0")) == Decimal("830.00"), f"2300={balances.get('2300')}"

        payslip_id = gen.json()["data"][0]["id"]

    # 4. Pay payslip by bank → 2300 closed, 1410 reduced
    pay = await client.post(f"/api/v1/hr/payslips/{payslip_id}/pay", json={"payment_date": "2026-08-31"}, headers=auth_headers)
    assert pay.status_code == 200, pay.text

    async with TestSessionLocal() as s:
        accounts = (await s.execute(select(GLAccount).where(GLAccount.company_id == test_company.id))).scalars().all()
        acc = {a.code: a for a in accounts}
        balances = {}
        for code, a in acc.items():
            row = (await s.execute(
                select(
                    func.coalesce(func.sum(JournalEntryLine.debit_amount), 0),
                    func.coalesce(func.sum(JournalEntryLine.credit_amount), 0),
                ).where(JournalEntryLine.gl_account_id == a.id)
            )).one()
            dr, cr = Decimal(row[0]), Decimal(row[1])
            balances[code] = dr - cr if a.account_type in ("asset", "expense") else cr - dr

        assert balances.get("2300", Decimal("0")) == Decimal("0.00"), f"2300={balances.get('2300')} (should be cleared)"
        assert balances.get("1410", Decimal("0")) == Decimal("-830.00"), f"1410={balances.get('1410')}"

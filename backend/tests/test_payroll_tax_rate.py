"""Regression: Georgian standard payroll income tax is 15% (flat rate)."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.hr import Employee


@pytest.mark.asyncio
async def test_standard_payroll_income_tax_is_fifteen_percent(
    client, db_session, test_company, auth_headers,
):
    employee = Employee(
        company_id=test_company.id,
        personal_number="01001001001",
        full_name="Payroll Tax Test",
        position="Accountant",
        hire_date=date(2026, 1, 1),
        status=Employee.Status.ACTIVE,
        base_salary=Decimal("3000.00"),
        salary_currency="GEL",
    )
    db_session.add(employee)
    await db_session.commit()

    response = await client.post(
        "/api/v1/hr/payroll/calculate",
        json={"year": 2026, "month": 8},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    row = response.json()["data"][0]
    assert Decimal(str(row["income_tax"])) == Decimal("450.00")  # 15% of 3000
    assert Decimal(str(row["pension_contribution"])) == Decimal("60.00")  # 2%
    assert Decimal(str(row["net_pay"])) == Decimal("2490.00")  # 3000 - 450 - 60

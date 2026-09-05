"""Sales Teams 2.0: commission approval, return adjustment, payroll link."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.hr import Payslip
from app.models.sales_team import CommissionAccrual, CommissionRule
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_accrual(client, auth_headers, test_company, db_session, amount=500.0, rate=5.0):
    """Create order + rule + accrual row (simulating order-confirmation accrual)."""
    from app.models.client import Client
    from app.models.product import Product
    async with TestSessionLocal() as session:
        cust = Client(company_id=test_company.id, name="Comm Cust", client_type="legal",
                      identification_code=f"CC-{uuid.uuid4().hex[:6]}", vat_status=False, status="active")
        prod = Product(company_id=test_company.id, sku=f"CP-{uuid.uuid4().hex[:6]}",
                       name="Comm Prod", sale_price=amount, current_stock=10)
        session.add_all([cust, prod])
        await session.commit()
        cust_id, prod_id = str(cust.id), str(prod.id)
    resp = await client.post("/api/v1/orders/", json={
        "client_id": cust_id,
        "items": [{"product_id": prod_id, "product_name": "Comm Prod", "quantity": 1,
                   "unit_price": amount, "discount_percent": 0}],
        "delivery_address": "Tbilisi", "notes": "comm2 test",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    order_id = resp.json()["data"]["id"]

    rule = await client.post("/api/v1/sales/commission-rules/", json={
        "name": f"წესი {uuid.uuid4().hex[:4]}", "rate_percent": rate, "fixed_amount": 0,
    }, headers=auth_headers)
    assert rule.status_code == 201, rule.text
    rule_id = rule.json()["data"]["id"]

    async with TestSessionLocal() as session:
        accrual = CommissionAccrual(
            company_id=test_company.id, rule_id=uuid.UUID(rule_id), order_id=uuid.UUID(order_id),
            base_amount=Decimal(str(amount)), commission_amount=Decimal(str(round(amount * rate / 100, 2))),
            status="accrued",
        )
        session.add(accrual)
        await session.commit()
        accrual_id = str(accrual.id)
    return accrual_id


async def test_commission_approval_flow(client, auth_headers, test_company, db_session):
    """საკომისიოს დადასტურება: accrued → approved → paid."""
    accrual_id = await _make_accrual(client, auth_headers, test_company, db_session, 500.0, 5.0)

    # approve
    r = await client.post(f"/api/v1/sales/commissions/{accrual_id}/approve",
                          json={"approve": True, "reason": "OK"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["status"] == "approved"
    assert d["approved_at"] is not None
    assert d["approved_by"] is not None

    # double approve → 400
    r2 = await client.post(f"/api/v1/sales/commissions/{accrual_id}/approve",
                           json={"approve": True}, headers=auth_headers)
    assert r2.status_code == 400

    # mark paid after approval
    r3 = await client.post(f"/api/v1/sales/commissions/{accrual_id}/mark-paid", headers=auth_headers)
    assert r3.status_code == 200
    assert r3.json()["data"]["status"] == "paid"


async def test_commission_reject(client, auth_headers, test_company, db_session):
    """საკომისიოს უარყოფა: accrued → cancelled."""
    accrual_id = await _make_accrual(client, auth_headers, test_company, db_session, 300.0, 10.0)
    r = await client.post(f"/api/v1/sales/commissions/{accrual_id}/approve",
                          json={"approve": False, "reason": "არასწორი თანხა"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"


async def test_commission_return_adjustment(client, auth_headers, test_company, db_session):
    """დაბრუნებისას საკომისიოს კორექტირება: ძველი იხურება, უარყოფითი ახალი იქმნება."""
    accrual_id = await _make_accrual(client, auth_headers, test_company, db_session, 1000.0, 5.0)

    r = await client.post(f"/api/v1/sales/commissions/{accrual_id}/adjust",
                          json={"reason": "შეკვეთა დაბრუნდა"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["status"] == "adjusted"
    assert d["commission_amount"] == -50.0  # clawback
    assert d["adjustment_of"] == accrual_id
    assert d["adjustment_reason"] == "შეკვეთა დაბრუნდა"

    # original is cancelled
    listed = await client.get("/api/v1/sales/commissions/", headers=auth_headers)
    items = listed.json()["data"]["items"]
    orig = next(i for i in items if i["id"] == accrual_id)
    assert orig["status"] == "cancelled"

    # paid commission cannot be adjusted
    paid_id = await _make_accrual(client, auth_headers, test_company, db_session, 200.0, 5.0)
    await client.post(f"/api/v1/sales/commissions/{paid_id}/mark-paid", headers=auth_headers)
    r2 = await client.post(f"/api/v1/sales/commissions/{paid_id}/adjust",
                           json={"reason": "დაბრუნება"}, headers=auth_headers)
    assert r2.status_code == 400


async def test_commission_payroll_link(client, auth_headers, test_company, db_session):
    """სახელფასო მოდულთან კავშირი: approved → paid payslip-ზე მიბმით."""
    accrual_id = await _make_accrual(client, auth_headers, test_company, db_session, 800.0, 5.0)
    await client.post(f"/api/v1/sales/commissions/{accrual_id}/approve",
                      json={"approve": True}, headers=auth_headers)

    # create a payslip directly
    from app.models.hr import Employee, PayrollEntry
    async with TestSessionLocal() as session:
        emp = Employee(company_id=test_company.id, personal_number=f"0100{uuid.uuid4().hex[:7]}",
                       full_name="გაყიდვების თანამშრომელი", position="გაყიდვების მენეჯერი",
                       email=f"emp-{uuid.uuid4().hex[:6]}@test.ge", hire_date=date.today())
        session.add(emp)
        await session.flush()
        entry = PayrollEntry(company_id=test_company.id, employee_id=emp.id,
                             period_year=2026, period_month=9, gross_pay=Decimal("1000"),
                             net_pay=Decimal("800"), status="draft")
        session.add(entry)
        await session.flush()
        payslip = Payslip(
            company_id=test_company.id, employee_id=emp.id, payroll_entry_id=entry.id,
            payslip_number=f"PS-{uuid.uuid4().hex[:6]}", period_year=2026, period_month=9,
            base_salary=Decimal("1000"), gross_pay=Decimal("1000"), net_pay=Decimal("800"),
            status="draft",
        )
        session.add(payslip)
        await session.commit()
        payslip_id = str(payslip.id)

    r = await client.post(f"/api/v1/sales/commissions/{accrual_id}/link-payslip",
                          json={"payslip_id": payslip_id}, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["payslip_id"] == payslip_id
    assert d["status"] == "paid"  # approved → paid on link
    assert d["paid_at"] is not None

    # invalid payslip → 404
    r2 = await client.post(f"/api/v1/sales/commissions/{accrual_id}/link-payslip",
                           json={"payslip_id": str(uuid.uuid4())}, headers=auth_headers)
    assert r2.status_code == 404

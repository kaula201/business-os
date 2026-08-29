"""Project timesheet billing — hourly rate, billed amounts, profitability roll-up."""
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.models.projects import Project, ProjectMember, ProjectTimesheet
from app.models.user import User
from app.core.security import hash_password
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_timesheet_billing_rolls_into_profitability(client, auth_headers, test_company):
    async with TestSessionLocal() as session:
        user = User(company_id=test_company.id, email=f"ts-{uuid.uuid4().hex[:6]}@demo.ge",
                    hashed_password=hash_password("pass12345"), full_name="TS User",
                    role=User.Role.EMPLOYEE)
        session.add(user)
        await session.flush()
        proj = Project(company_id=test_company.id, code=f"PRJ-{uuid.uuid4().hex[:4]}",
                       name="Billing Project", budget_amount=5000)
        session.add(proj)
        await session.flush()
        session.add(ProjectMember(company_id=test_company.id, project_id=proj.id,
                                  user_id=user.id, role="consultant", hourly_rate=60))
        await session.commit()
        pid, uid = str(proj.id), str(user.id)

    # billable entry: 10h × 150 rate → billed 1500, revenue +1500, cost +600 (member 60)
    ts = await client.post(f"/api/v1/projects/{pid}/timesheets", json={
        "user_id": uid, "work_date": "2026-08-29", "hours": 10,
        "billable": True, "hourly_rate": 150, "description": "test",
    }, headers=auth_headers)
    assert ts.status_code == 201, ts.text
    data = ts.json()["data"]
    assert float(data["hourly_rate"]) == 150.0
    assert float(data["billed_amount"]) == 1500.0

    # billing summary reflects unbilled value
    bs = await client.get(f"/api/v1/projects/{pid}/billing-summary", headers=auth_headers)
    s = bs.json()["data"]
    assert float(s["billable_hours"]) == 10.0
    assert float(s["unbilled_value"]) == 1500.0
    assert float(s["project_revenue"]) == 1500.0
    assert float(s["project_spent"]) == 600.0

    # profitability: profit = 1500 - 600
    pr = await client.get(f"/api/v1/projects/{pid}/profitability", headers=auth_headers)
    p = pr.json()["data"]
    assert float(p["profitability"]) == 900.0
    assert float(p["revenue_amount"]) == 1500.0

    # mark billed
    mb = await client.post(f"/api/v1/projects/{pid}/timesheets/{data['id']}/mark-billed", headers=auth_headers)
    assert mb.status_code == 200
    assert mb.json()["data"]["billed"] is True

    # double billing rejected
    again = await client.post(f"/api/v1/projects/{pid}/timesheets/{data['id']}/mark-billed", headers=auth_headers)
    assert again.status_code == 409

    # summary now shows billed, unbilled 0
    bs2 = await client.get(f"/api/v1/projects/{pid}/billing-summary", headers=auth_headers)
    s2 = bs2.json()["data"]
    assert float(s2["billed_value"]) == 1500.0
    assert float(s2["unbilled_value"]) == 0.0


async def test_non_billable_timesheet_no_revenue(client, auth_headers, test_company):
    async with TestSessionLocal() as session:
        proj = Project(company_id=test_company.id, code=f"PRJ-{uuid.uuid4().hex[:4]}",
                       name="Internal Project")
        session.add(proj)
        await session.commit()
        pid = str(proj.id)

    ts = await client.post(f"/api/v1/projects/{pid}/timesheets", json={
        "work_date": "2026-08-29", "hours": 5, "billable": False, "description": "internal",
    }, headers=auth_headers)
    assert ts.status_code == 201, ts.text
    assert float(ts.json()["data"]["billed_amount"]) == 0.0

    pr = await client.get(f"/api/v1/projects/{pid}/profitability", headers=auth_headers)
    assert float(pr.json()["data"]["revenue_amount"]) == 0.0

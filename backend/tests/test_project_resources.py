"""Project resource planning — members, timesheets, utilization."""
import uuid
from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


async def _create_project(client, auth_headers) -> str:
    resp = await client.post("/api/v1/projects/", json={
        "code": f"PRJ-{uuid.uuid4().hex[:6]}",
        "name": f"პროექტი-{uuid.uuid4().hex[:4]}",
        "budget_amount": 10000,
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def test_project_member_crud(client, auth_headers, test_admin):
    pid = await _create_project(client, auth_headers)

    add = await client.post(f"/api/v1/projects/{pid}/members", json={
        "user_id": str(test_admin.id), "role": "lead",
        "allocation_percent": 50, "hourly_rate": 80,
    }, headers=auth_headers)
    assert add.status_code == 201, add.text
    member_id = add.json()["data"]["id"]

    lst = await client.get(f"/api/v1/projects/{pid}/members", headers=auth_headers)
    assert lst.status_code == 200
    members = lst.json()["data"]
    assert len(members) == 1
    assert members[0]["role"] == "lead"
    assert float(members[0]["allocation_percent"]) == 50.0
    assert members[0]["user_name"] is not None

    upd = await client.patch(f"/api/v1/projects/members/{member_id}", json={
        "allocation_percent": 75, "role": "manager",
    }, headers=auth_headers)
    assert upd.status_code == 200, upd.text

    lst2 = await client.get(f"/api/v1/projects/{pid}/members", headers=auth_headers)
    assert float(lst2.json()["data"][0]["allocation_percent"]) == 75.0
    assert lst2.json()["data"][0]["role"] == "manager"

    rem = await client.delete(f"/api/v1/projects/members/{member_id}", headers=auth_headers)
    assert rem.status_code == 200, rem.text
    lst3 = await client.get(f"/api/v1/projects/{pid}/members", headers=auth_headers)
    assert len(lst3.json()["data"]) == 0


async def test_timesheet_flow(client, auth_headers, test_admin):
    pid = await _create_project(client, auth_headers)
    await client.post(f"/api/v1/projects/{pid}/members", json={
        "user_id": str(test_admin.id), "role": "member",
        "allocation_percent": 100, "hourly_rate": 100,
    }, headers=auth_headers)

    add = await client.post(f"/api/v1/projects/{pid}/timesheets", json={
        "user_id": str(test_admin.id),
        "work_date": date.today().isoformat(),
        "hours": 8, "billable": True, "description": "სამუშაო დღე",
    }, headers=auth_headers)
    assert add.status_code == 201, add.text

    lst = await client.get(f"/api/v1/projects/{pid}/timesheets", headers=auth_headers)
    assert lst.status_code == 200
    data = lst.json()["data"]
    assert float(data["total_hours"]) == 8.0
    assert len(data["items"]) == 1
    assert data["items"][0]["hours"] == 8.0

    # spent_amount was rolled up (8h * 100 GEL/h)
    detail = await client.get(f"/api/v1/projects/{pid}/profitability", headers=auth_headers)
    assert detail.status_code == 200
    assert float(detail.json()["data"]["spent_amount"]) == 800.0


async def test_resource_utilization(client, auth_headers, test_admin):
    pid = await _create_project(client, auth_headers)
    await client.post(f"/api/v1/projects/{pid}/members", json={
        "user_id": str(test_admin.id), "role": "lead",
        "allocation_percent": 60,
    }, headers=auth_headers)

    util = await client.get("/api/v1/projects/resources/utilization", headers=auth_headers)
    assert util.status_code == 200, util.text
    rows = util.json()["data"]
    me = next((r for r in rows if r["user_id"] == str(test_admin.id)), None)
    assert me is not None
    assert float(me["total_allocation"]) == 60.0
    assert me["project_count"] == 1

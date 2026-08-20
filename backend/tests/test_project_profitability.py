"""Project profitability — revenue - spent, margin %."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_project_profitability(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/projects/", json={
        "code": "PRF-1", "name": "Profit Project",
        "budget_amount": 10000, "revenue_amount": 12000, "spent_amount": 8000,
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["data"]["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}/profitability", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["revenue_amount"] == 12000.0
    assert data["spent_amount"] == 8000.0
    assert data["profitability"] == 4000.0  # 12000 - 8000
    assert data["profitability_percent"] == 33.33  # 4000/12000
    assert data["budget_remaining"] == 2000.0  # 10000 - 8000

    # update revenue → profitability recalculates
    resp = await client.patch(f"/api/v1/projects/{project_id}", json={"revenue_amount": 10000}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.get(f"/api/v1/projects/{project_id}/profitability", headers=auth_headers)
    data = resp.json()["data"]
    assert data["profitability"] == 2000.0
    assert data["profitability_percent"] == 20.0

"""P1-8: Report builder — definitions, saved views, scheduled delivery."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def test_report_builder_saved_and_schedule(client, auth_headers, test_company):
    # 1. Definitions available
    defs = await client.get("/api/v1/reports/definitions", headers=auth_headers)
    assert defs.status_code == 200, defs.text
    assert len(defs.json()["data"]) > 0, "no metric definitions"

    # 2. Save a report view
    saved = await client.post("/api/v1/reports/saved", json={
        "name": "Weekly Revenue", "metric": "revenue", "params": {"period": "30d"},
    }, headers=auth_headers)
    assert saved.status_code == 201, saved.text
    saved_id = saved.json()["data"]["id"]

    # 3. List saved views
    listed = await client.get("/api/v1/reports/saved", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    assert any(r["id"] == saved_id for r in listed.json()["data"])

    # 4. Schedule delivery
    sched = await client.post("/api/v1/reports/schedules", json={
        "report_id": saved_id, "frequency": "weekly", "recipients": "boss@demo.ge",
    }, headers=auth_headers)
    assert sched.status_code == 201, sched.text
    sched_id = sched.json()["data"]["id"]

    # 5. List schedules
    scheds = await client.get("/api/v1/reports/schedules", headers=auth_headers)
    assert scheds.status_code == 200, scheds.text
    assert any(s["id"] == sched_id for s in scheds.json()["data"])

    # 6. Delete saved view
    deleted = await client.delete(f"/api/v1/reports/saved/{saved_id}", headers=auth_headers)
    assert deleted.status_code == 200, deleted.text

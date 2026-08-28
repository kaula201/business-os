"""Field-service mobile — job lifecycle: create → start → complete, my-jobs."""
import uuid
from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


async def _create_job(client, auth_headers, technician_id: str | None = None) -> dict:
    payload = {
        "scheduled_date": date.today().isoformat(),
        "priority": "high",
        "address": "თბილისი, ვაჟა-ფშაველა 45",
        "notes": "კონდიციონერის შეკეთება",
    }
    if technician_id:
        payload["technician_id"] = technician_id
    resp = await client.post("/api/v1/helpdesk/field-service", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_field_service_lifecycle(client, auth_headers, test_admin):
    job = await _create_job(client, auth_headers, technician_id=str(test_admin.id))
    job_id = job["id"]
    assert job["status"] == "scheduled"

    start = await client.post(f"/api/v1/helpdesk/field-service/{job_id}/start", headers=auth_headers)
    assert start.status_code == 200, start.text
    assert start.json()["data"]["status"] == "in_progress"

    complete = await client.post(f"/api/v1/helpdesk/field-service/{job_id}/complete", json={
        "work_summary": "კომპრესორი გამოვცვალე, სისტემა გავტესტე",
        "client_signature": "გიორგი ბერიძე",
    }, headers=auth_headers)
    assert complete.status_code == 200, complete.text
    assert complete.json()["data"]["status"] == "completed"

    # double complete → 400
    again = await client.post(f"/api/v1/helpdesk/field-service/{job_id}/complete", json={
        "work_summary": "x",
    }, headers=auth_headers)
    assert again.status_code == 400

    lst = await client.get("/api/v1/helpdesk/field-service", headers=auth_headers)
    assert lst.status_code == 200, lst.text
    rows = lst.json()["data"]
    done = next((r for r in rows if r["id"] == job_id), None)
    assert done is not None
    assert done["status"] == "completed"
    assert done["client_signature"] == "გიორგი ბერიძე"
    assert done["priority"] == "high"
    assert done["completed_at"] is not None


async def test_field_service_filters(client, auth_headers, test_admin):
    await _create_job(client, auth_headers, technician_id=str(test_admin.id))
    await _create_job(client, auth_headers)  # unassigned

    by_tech = await client.get(
        "/api/v1/helpdesk/field-service",
        params={"technician_id": str(test_admin.id)},
        headers=auth_headers,
    )
    assert by_tech.status_code == 200
    assert len(by_tech.json()["data"]) == 1

    by_status = await client.get(
        "/api/v1/helpdesk/field-service", params={"status": "scheduled"}, headers=auth_headers
    )
    assert by_status.status_code == 200
    assert all(r["status"] == "scheduled" for r in by_status.json()["data"])


async def test_my_jobs_and_not_completed(client, auth_headers, test_admin):
    j1 = await _create_job(client, auth_headers, technician_id=str(test_admin.id))
    # complete one so it drops out of my-jobs
    await client.post(f"/api/v1/helpdesk/field-service/{j1['id']}/complete", json={
        "work_summary": "შესრულდა",
    }, headers=auth_headers)
    await _create_job(client, auth_headers, technician_id=str(test_admin.id))

    mine = await client.get("/api/v1/helpdesk/field-service/my-jobs", headers=auth_headers)
    assert mine.status_code == 200, mine.text
    jobs = mine.json()["data"]
    assert len(jobs) == 1  # only the scheduled one
    assert all(j["status"] in ("scheduled", "in_progress") for j in jobs)

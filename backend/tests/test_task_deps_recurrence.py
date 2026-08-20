"""Task dependencies (blocking) and recurrence auto-generation."""
import pytest
from sqlalchemy import select

from app.models.task import Task, TaskDependency
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_task(client, auth_headers, title="T", **extra):
    resp = await client.post("/api/v1/tasks/", json={"title": title, **extra}, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def test_dependency_blocks_start(client, auth_headers, test_company, db_session):
    a = await _make_task(client, auth_headers, "Design")
    b = await _make_task(client, auth_headers, "Build")

    # b blocked_by a
    resp = await client.post(f"/api/v1/tasks/{b}/dependencies", json={
        "depends_on_task_id": a, "dependency_type": "blocked_by",
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text

    # b cannot start while a is todo
    resp = await client.patch(f"/api/v1/tasks/{b}", json={"status": "in_progress"}, headers=auth_headers)
    assert resp.status_code == 409, resp.text
    assert "დაბლოკილია" in resp.json()["detail"]

    # complete a → b can start
    resp = await client.patch(f"/api/v1/tasks/{a}", json={"status": "done"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.patch(f"/api/v1/tasks/{b}", json={"status": "in_progress"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text


async def test_recurring_task_auto_creates_next(client, auth_headers, test_company, db_session):
    from datetime import datetime, timedelta
    due = (datetime.utcnow() + timedelta(days=1)).isoformat()
    tid = await _make_task(client, auth_headers, "Weekly report", recurrence="weekly", due_date=due)

    resp = await client.patch(f"/api/v1/tasks/{tid}", json={"status": "done"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text

    async with TestSessionLocal() as s:
        tasks = (await s.execute(select(Task).where(Task.title == "Weekly report"))).scalars().all()
        assert len(tasks) == 2  # original + auto-created next
        next_task = [t for t in tasks if t.status == "todo"][0]
        assert next_task.recurrence == "weekly"
        assert next_task.due_date and tasks[0].due_date and next_task.due_date > tasks[0].due_date

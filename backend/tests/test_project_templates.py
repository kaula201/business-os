"""Project templates — create template, instantiate project from it."""
import pytest
from sqlalchemy import select

from app.models.projects import Project, ProjectMilestone, ProjectTemplate
from app.models.task import Task
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_template_lifecycle(client, auth_headers, test_company, db_session):
    # create template with 2 milestones + tasks
    resp = await client.post("/api/v1/projects/templates", json={
        "name": "Website Build",
        "description": "Standard website delivery",
        "default_budget": 5000,
        "milestones": [
            {"name": "Discovery", "tasks": [
                {"title": "Requirements gathering", "priority": "high"},
                {"title": "Wireframes", "priority": "medium"},
            ]},
            {"name": "Build", "tasks": [
                {"title": "Frontend", "priority": "high"},
            ]},
        ],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    template_id = resp.json()["data"]["id"]

    # list templates
    resp = await client.get("/api/v1/projects/templates", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    templates = resp.json()["data"]
    assert len(templates) == 1
    assert len(templates[0]["milestones"]) == 2
    assert len(templates[0]["milestones"][0]["tasks"]) == 2

    # instantiate → project with milestones + tasks
    resp = await client.post(f"/api/v1/projects/templates/{template_id}/instantiate", json={
        "name": "Client Website", "code": "WEB-001", "budget_amount": 6000,
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["milestones_created"] == 2

    async with TestSessionLocal() as s:
        proj = (await s.execute(select(Project).where(Project.id == project_id))).scalar_one()
        assert proj.budget_amount == 6000
        milestones = (await s.execute(select(ProjectMilestone).where(ProjectMilestone.project_id == project_id))).scalars().all()
        assert len(milestones) == 2
        tasks = (await s.execute(select(Task).where(Task.project_id == project_id))).scalars().all()
        assert len(tasks) == 3
        assert all(t.status == "todo" for t in tasks)

    # delete template
    resp = await client.delete(f"/api/v1/projects/templates/{template_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.get("/api/v1/projects/templates", headers=auth_headers)
    assert len(resp.json()["data"]) == 0

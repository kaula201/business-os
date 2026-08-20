"""Helpdesk teams + customizable pipelines (Odoo-style)."""
import pytest
from sqlalchemy import select

from app.models.helpdesk import HelpdeskTicket
from app.models.helpdesk_ext import HelpdeskPipeline, HelpdeskTeam
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_team_lifecycle(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/helpdesk/teams", json={
        "name": "Support L1", "description": "First line",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    team_id = resp.json()["data"]["id"]

    resp = await client.get("/api/v1/helpdesk/teams", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    teams = resp.json()["data"]
    assert len(teams) == 1
    assert teams[0]["name"] == "Support L1"

    resp = await client.delete(f"/api/v1/helpdesk/teams/{team_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text


async def test_pipeline_and_ticket_assignment(client, auth_headers, test_company, db_session):
    # pipeline with 3 stages
    resp = await client.post("/api/v1/helpdesk/pipelines", json={
        "name": "Support Flow",
        "stages": ["New", "Triaged", "Done"],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    pipeline_id = resp.json()["data"]["id"]

    resp = await client.get("/api/v1/helpdesk/pipelines", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    pipelines = resp.json()["data"]
    assert len(pipelines) == 1
    assert len(pipelines[0]["stages"]) == 3
    assert pipelines[0]["stages"][-1]["is_done"] is True  # last stage is done

    # team
    resp = await client.post("/api/v1/helpdesk/teams", json={"name": "Support L2"}, headers=auth_headers)
    team_id = resp.json()["data"]["id"]

    # ticket assigned to team + first stage
    resp = await client.post("/api/v1/helpdesk/", json={
        "subject": "Printer broken",
        "priority": "high",
        "team_id": team_id,
        "pipeline_stage_id": pipelines[0]["stages"][0]["id"],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    ticket = resp.json()["data"]
    assert ticket["team_name"] == "Support L2"
    assert ticket["pipeline_stage_name"] == "New"

    async with TestSessionLocal() as s:
        t = (await s.execute(select(HelpdeskTicket).where(HelpdeskTicket.id == ticket["id"]))).scalar_one()
        assert t.team_id is not None
        assert t.pipeline_stage_id is not None

    # move ticket to next stage
    resp = await client.put(f"/api/v1/helpdesk/{ticket['id']}", json={
        "pipeline_stage_id": pipelines[0]["stages"][1]["id"],
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["pipeline_stage_name"] == "Triaged"

    # delete pipeline
    resp = await client.delete(f"/api/v1/helpdesk/pipelines/{pipeline_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text

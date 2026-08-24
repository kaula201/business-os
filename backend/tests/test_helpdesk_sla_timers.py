"""P1-6: Helpdesk SLA timers — auto-assignment on ticket creation."""
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.helpdesk import HelpdeskTicket
from app.models.helpdesk_ext import HelpdeskSla
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_helpdesk_sla_timer_auto_assignment(client, auth_headers, test_company):
    # 1. Create an SLA for high priority: 4h response / 24h resolution
    sla = await client.post("/api/v1/helpdesk/slas", json={
        "name": "High SLA", "priority": "high", "response_hours": 4, "resolution_hours": 24,
    }, headers=auth_headers)
    assert sla.status_code == 201, sla.text

    # 2. Create a high-priority ticket → SLA auto-assigned + deadlines set
    ticket = await client.post("/api/v1/helpdesk/", json={
        "subject": "Urgent issue", "priority": "high",
    }, headers=auth_headers)
    assert ticket.status_code == 201, ticket.text
    ticket_id = ticket.json()["data"]["id"]

    # 3. Verify deadlines on the ticket
    async with TestSessionLocal() as s:
        t = (await s.execute(select(HelpdeskTicket).where(HelpdeskTicket.id == ticket_id))).scalar_one()
        assert t.sla_id is not None, "SLA not auto-assigned"
        assert t.response_deadline is not None, "response deadline missing"
        assert t.resolution_deadline is not None, "resolution deadline missing"
        hours = (t.resolution_deadline - t.response_deadline).total_seconds() / 3600
        assert hours == 20.0, f"expected 20h gap, got {hours}"  # 24 - 4

    # 4. Low-priority ticket without SLA → no deadlines
    ticket2 = await client.post("/api/v1/helpdesk/", json={
        "subject": "Minor issue", "priority": "low",
    }, headers=auth_headers)
    assert ticket2.status_code == 201, ticket2.text
    async with TestSessionLocal() as s:
        t2 = (await s.execute(select(HelpdeskTicket).where(HelpdeskTicket.id == ticket2.json()["data"]["id"]))).scalar_one()
        assert t2.sla_id is None, "low priority should have no SLA"

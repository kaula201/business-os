"""P1.6: Helpdesk rich tickets — category/source/tags, messages, followers, real attachments, time, satisfaction, KB."""
import io
import uuid

import pytest
from sqlalchemy import select

from app.models.helpdesk_ext import KnowledgeArticle
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed_kb(test_company) -> str:
    async with TestSessionLocal() as session:
        art = KnowledgeArticle(company_id=test_company.id, title="პაროლის აღდგენა", content="პაროლის აღდგენის ინსტრუქცია", is_published=True)
        session.add(art)
        await session.commit()
        return str(art.id)


async def test_rich_ticket_create_and_update(client, auth_headers, test_company):
    t = await client.post("/api/v1/helpdesk/", json={
        "subject": "პაროლის პრობლემა", "priority": "high",
        "category": "bug", "ticket_type": "technical", "source_channel": "email",
        "tags": ["auth", "urgent"],
    }, headers=auth_headers)
    assert t.status_code == 201, t.text
    data = t.json()["data"]
    assert data["category"] == "bug"
    assert data["ticket_type"] == "technical"
    assert data["source_channel"] == "email"
    assert data["tags"] == ["auth", "urgent"]
    ticket_id = data["id"]

    # update: time spent + satisfaction
    ts = await client.post(f"/api/v1/helpdesk/{ticket_id}/time-spent", json={"minutes": 45}, headers=auth_headers)
    assert ts.status_code == 200, ts.text
    assert ts.json()["data"]["time_spent_minutes"] == 45

    sat = await client.post(f"/api/v1/helpdesk/{ticket_id}/satisfaction", json={"score": 5, "comment": "შესანიშნავი"}, headers=auth_headers)
    assert sat.status_code == 200, sat.text

    got = await client.get(f"/api/v1/helpdesk/{ticket_id}", headers=auth_headers)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["time_spent_minutes"] == 45
    assert got.json()["data"]["satisfaction_score"] == 5


async def test_messages_and_followers(client, auth_headers, test_company):
    t = await client.post("/api/v1/helpdesk/", json={"subject": "Thread test"}, headers=auth_headers)
    ticket_id = t.json()["data"]["id"]

    m = await client.post(f"/api/v1/helpdesk/{ticket_id}/messages", json={
        "body": "გამარჯობა, პრობლემა მაქვს", "direction": "inbound", "channel": "email",
    }, headers=auth_headers)
    assert m.status_code == 201, m.text

    msgs = await client.get(f"/api/v1/helpdesk/{ticket_id}/messages", headers=auth_headers)
    assert msgs.status_code == 200
    assert len(msgs.json()["data"]) == 1
    assert msgs.json()["data"][0]["channel"] == "email"

    # follower
    from app.models.user import User
    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.company_id == test_company.id).limit(1))).scalar_one()
        uid = str(user.id)
    f = await client.post(f"/api/v1/helpdesk/{ticket_id}/followers", json={"user_id": uid}, headers=auth_headers)
    assert f.status_code == 201, f.text
    dup = await client.post(f"/api/v1/helpdesk/{ticket_id}/followers", json={"user_id": uid}, headers=auth_headers)
    assert dup.status_code == 409
    fl = await client.get(f"/api/v1/helpdesk/{ticket_id}/followers", headers=auth_headers)
    assert len(fl.json()["data"]) == 1


async def test_real_attachment_upload(client, auth_headers, test_company):
    t = await client.post("/api/v1/helpdesk/", json={"subject": "Attachment test"}, headers=auth_headers)
    ticket_id = t.json()["data"]["id"]

    up = await client.post(
        f"/api/v1/helpdesk/{ticket_id}/attachments",
        files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 fake content"), "application/pdf")},
        headers=auth_headers,
    )
    assert up.status_code == 201, up.text
    assert up.json()["data"]["filename"] == "report.pdf"
    assert up.json()["data"]["size_bytes"] > 0

    atts = await client.get(f"/api/v1/helpdesk/{ticket_id}/attachments", headers=auth_headers)
    assert atts.status_code == 200
    assert len(atts.json()["data"]) == 1


async def test_kb_suggestions(client, auth_headers, test_company):
    await _seed_kb(test_company)
    t = await client.post("/api/v1/helpdesk/", json={"subject": "პაროლის აღდგენა არ მუშაობს", "description": "პაროლი დავივიწყე"}, headers=auth_headers)
    ticket_id = t.json()["data"]["id"]
    kb = await client.get(f"/api/v1/helpdesk/{ticket_id}/kb-suggestions", headers=auth_headers)
    assert kb.status_code == 200, kb.text
    assert len(kb.json()["data"]) >= 1, "KB suggestion expected"

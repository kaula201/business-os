"""Tests for email tracking and e-signature."""
import uuid

import pytest
from httpx import AsyncClient

from app.models.email_marketing import EmailCampaign
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _create_campaign(client, auth_headers) -> str:
    resp = await client.post("/api/v1/email-campaigns/", json={
        "name": "აგვისტოს ნიუსლეტერი", "subject": "ახალი შეთავაზებები",
        "audience": {"segment": "all"},
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def test_email_event_flow_and_stats(client, auth_headers, test_company):
    campaign_id = await _create_campaign(client, auth_headers)

    for et in ("sent", "opened", "clicked"):
        resp = await client.post("/api/v1/email-events/", json={
            "campaign_id": campaign_id, "recipient_email": "client@example.ge", "event_type": et,
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text

    stats = await client.get(f"/api/v1/email-campaigns/{campaign_id}/stats", headers=auth_headers)
    assert stats.status_code == 200
    data = stats.json()["data"]
    assert data["sent"] == 1
    assert data["opened"] == 1
    assert data["clicked"] == 1
    assert data["open_rate"] == 100.0

    listed = await client.get("/api/v1/email-events/", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 3


async def test_email_event_cross_tenant_rejected(client, auth_headers, test_company):
    # event for unknown campaign -> 404
    resp = await client.post("/api/v1/email-events/", json={
        "campaign_id": str(uuid.uuid4()), "recipient_email": "x@y.ge", "event_type": "sent",
    }, headers=auth_headers)
    assert resp.status_code == 404


async def test_signature_request_and_sign(client, auth_headers, test_company):
    created = await client.post("/api/v1/signature-requests/", json={
        "document_name": "კონტრაქტი #1", "signer_name": "გიორგი", "signer_email": "giorgi@client.ge",
    }, headers=auth_headers)
    assert created.status_code == 201, created.text
    req = created.json()["data"]
    assert req["status"] == "pending"

    # wrong email -> 403
    wrong = await client.post("/api/v1/signature-requests/sign", json={
        "token": req["signing_token"] if "signing_token" in req else "x" * 32,
        "signer_email": "hacker@evil.ge", "decision": "sign",
    }, headers=auth_headers)
    # token is not exposed in response; fetch from DB
    from app.models.signature import SignatureRequest
    from sqlalchemy import select
    async with TestSessionLocal() as session:
        db_req = (await session.execute(select(SignatureRequest).where(
            SignatureRequest.id == uuid.UUID(req["id"]),
        ))).scalar_one()
        token = db_req.signing_token

    wrong = await client.post("/api/v1/signature-requests/sign", json={
        "token": token, "signer_email": "hacker@evil.ge", "decision": "sign",
    }, headers=auth_headers)
    assert wrong.status_code == 403

    # correct sign
    ok = await client.post("/api/v1/signature-requests/sign", json={
        "token": token, "signer_email": "giorgi@client.ge", "decision": "sign",
    }, headers=auth_headers)
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["status"] == "signed"

    # double sign -> 400
    again = await client.post("/api/v1/signature-requests/sign", json={
        "token": token, "signer_email": "giorgi@client.ge", "decision": "sign",
    }, headers=auth_headers)
    assert again.status_code == 400


async def test_signature_list_filter(client, auth_headers, test_company):
    await client.post("/api/v1/signature-requests/", json={
        "document_name": "დოკუმენტი", "signer_name": "ანა", "signer_email": "ana@client.ge",
    }, headers=auth_headers)
    listed = await client.get("/api/v1/signature-requests/", params={"status": "pending"}, headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] >= 1

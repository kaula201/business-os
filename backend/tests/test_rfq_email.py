"""RFQ supplier assignment + email sending (sandbox)."""
import uuid

import pytest
from sqlalchemy import select

from app.models.email_calendar import EmailMessage
from app.models.procurement import RFQ
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _create_supplier(client, auth_headers, suffix: str, email: str | None = None):
    payload = {
        "name": f"RFQ Supplier {suffix}", "code": f"RFS-{suffix}",
        "identification_code": f"RID-{suffix}", "is_vat_payer": True,
    }
    if email:
        payload["email"] = email
    resp = await client.post("/api/v1/suppliers/", json=payload, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_product(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/products/", json={
        "sku": f"RFQP-{suffix}", "name": f"RFQ Product {suffix}", "sale_price": 10,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def test_rfq_supplier_assignment_and_email_send(client, auth_headers, test_company, db_session):
    supplier = await _create_supplier(client, auth_headers, "A", email="vendor-a@example.com")
    product = await _create_product(client, auth_headers, "A")

    created = await client.post("/api/v1/procurement/rfqs", json={
        "title": "RFQ Email Test", "supplier_id": supplier["id"],
        "required_date": "2026-09-01",
        "lines": [{"product_id": product["id"], "quantity": 5, "expected_price": 20}],
    }, headers=auth_headers)
    assert created.status_code == 201, created.text
    rfq_id = created.json()["data"]["id"]

    # supplier_id persisted on the RFQ row
    async with TestSessionLocal() as s:
        rfq = (await s.execute(select(RFQ).where(RFQ.id == uuid.UUID(rfq_id)))).scalar_one()
        assert rfq.supplier_id == uuid.UUID(supplier["id"])
        assert rfq.status == "draft"

    sent = await client.post(f"/api/v1/procurement/rfqs/{rfq_id}/send-email", headers=auth_headers)
    assert sent.status_code == 200, sent.text
    data = sent.json()["data"]
    assert data["to_email"] == "vendor-a@example.com"
    assert "RFQ" in data["subject"]
    assert data["status"] == "sent"

    # email message row persisted + RFQ status flipped to sent
    async with TestSessionLocal() as s:
        msg = (await s.execute(select(EmailMessage).where(EmailMessage.id == uuid.UUID(data["id"])))).scalar_one()
        assert msg.to_email == "vendor-a@example.com"
        assert "RFQ Product A" in msg.body
        assert "RFQ-" in msg.body
        rfq = (await s.execute(select(RFQ).where(RFQ.id == uuid.UUID(rfq_id)))).scalar_one()
        assert rfq.status == "sent"


async def test_rfq_email_requires_supplier_and_email(client, auth_headers, test_company, db_session):
    product = await _create_product(client, auth_headers, "B")
    supplier_no_email = await _create_supplier(client, auth_headers, "B")

    created = await client.post("/api/v1/procurement/rfqs", json={
        "title": "RFQ No Email", "supplier_id": supplier_no_email["id"],
        "lines": [{"product_id": product["id"], "quantity": 2, "expected_price": 10}],
    }, headers=auth_headers)
    assert created.status_code == 201, created.text
    rfq_id = created.json()["data"]["id"]

    # supplier without email -> 422
    sent = await client.post(f"/api/v1/procurement/rfqs/{rfq_id}/send-email", headers=auth_headers)
    assert sent.status_code == 422, sent.text

    # RFQ without supplier -> 422
    created2 = await client.post("/api/v1/procurement/rfqs", json={
        "title": "RFQ No Supplier",
        "lines": [{"product_id": product["id"], "quantity": 2, "expected_price": 10}],
    }, headers=auth_headers)
    assert created2.status_code == 201, created2.text
    sent2 = await client.post(f"/api/v1/procurement/rfqs/{created2.json()['data']['id']}/send-email", headers=auth_headers)
    assert sent2.status_code == 422, sent2.text

    # unknown RFQ -> 404
    sent3 = await client.post(f"/api/v1/procurement/rfqs/{uuid.uuid4()}/send-email", headers=auth_headers)
    assert sent3.status_code == 404, sent3.text

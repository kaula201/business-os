"""POS receipt by email — sandbox mode (no SMTP configured)."""
import pytest
from sqlalchemy import select

from app.models.email_calendar import EmailMessage
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_email_receipt_sandbox(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Email Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "Email Product", "sku": "EML-1", "sale_price": 50,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]

    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 2, "unit_price": 50}],
        "payment_method": "cash",
    }, headers=auth_headers)
    order = resp.json()["data"]

    resp = await client.post(
        f"/api/v1/pos/orders/{order['id']}/email-receipt",
        params={"to_email": "client@example.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "sent"  # sandbox

    async with TestSessionLocal() as s:
        m = (await s.execute(select(EmailMessage).where(EmailMessage.id == data["id"]))).scalar_one()
        assert m.to_email == "client@example.com"
        assert "ჩეკი" in m.subject
        assert "118.00" in m.body  # 100 + 18% VAT

"""P1-7: Webhook execution log — delivery success/failure recorded."""
import asyncio
import json
import uuid

import pytest
from sqlalchemy import select

from app.models.integration import Webhook, WebhookEvent
from app.services.webhook_delivery import deliver_webhook
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_webhook(db, company_id, url: str, events: str = "*") -> Webhook:
    wh = Webhook(company_id=company_id, name="Test WH", url=url, events=events, secret="s3cret")
    db.add(wh)
    await db.flush()
    return wh


async def test_webhook_delivery_success_and_failure(client, auth_headers, test_company):
    # local echo server
    async def handler(reader, writer):
        await reader.read(65536)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    async with TestSessionLocal() as s:
        wh_ok = await _make_webhook(s, test_company.id, f"http://127.0.0.1:{port}/hook")
        wh_bad = await _make_webhook(s, test_company.id, "http://127.0.0.1:1/nope")  # unreachable
        await s.commit()

        # success
        ev_ok = await deliver_webhook(s, test_company.id, wh_ok, "invoice.created", {"id": "x"})
        assert ev_ok.status == "delivered", ev_ok.last_error
        assert ev_ok.attempts == 1
        assert ev_ok.last_response_code == 200

        # failure
        ev_bad = await deliver_webhook(s, test_company.id, wh_bad, "invoice.created", {"id": "y"})
        assert ev_bad.status == "failed"
        assert ev_bad.attempts == 1
        assert ev_bad.last_error, "error message should be logged"

        # execution log persisted
        events = (await s.execute(select(WebhookEvent).where(WebhookEvent.company_id == test_company.id))).scalars().all()
        assert len(events) == 2

    server.close()
    await server.wait_closed()

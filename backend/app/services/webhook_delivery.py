"""Webhook delivery — send events to registered webhooks with execution logging."""
import json
import uuid
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Webhook, WebhookEvent


async def deliver_webhook(
    db: AsyncSession,
    company_id: uuid.UUID,
    webhook: Webhook,
    event_type: str,
    payload: dict,
) -> WebhookEvent:
    """Create an execution log entry and deliver the event (Odoo-style webhook log)."""
    event = WebhookEvent(
        company_id=company_id,
        webhook_id=webhook.id,
        event_type=event_type,
        payload=json.dumps(payload, ensure_ascii=False, default=str),
        status="pending",
        attempts=0,
    )
    db.add(event)
    await db.flush()

    headers = {"Content-Type": "application/json"}
    if webhook.secret:
        headers["X-Webhook-Secret"] = webhook.secret

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook.url, json=payload, headers=headers)
        event.attempts += 1
        event.status = "delivered" if resp.status_code < 400 else "failed"
        event.last_response_code = resp.status_code
        event.last_error = None if resp.status_code < 400 else resp.text[:500]
    except Exception as exc:  # noqa: BLE001 — network errors are logged, not raised
        event.attempts += 1
        event.status = "failed"
        event.last_error = str(exc)[:500]

    await db.flush()
    return event


async def deliver_event_to_matching_webhooks(
    db: AsyncSession,
    company_id: uuid.UUID,
    event_type: str,
    payload: dict,
) -> list[WebhookEvent]:
    """Deliver an event to every active webhook subscribed to that event type."""
    webhooks = (await db.execute(
        select(Webhook).where(
            Webhook.company_id == company_id,
            Webhook.is_active.is_(True),
        )
    )).scalars().all()
    results = []
    for wh in webhooks:
        subscribed = [e.strip() for e in (wh.events or "").split(",") if e.strip()]
        if "*" in subscribed or event_type in subscribed:
            results.append(await deliver_webhook(db, company_id, wh, event_type, payload))
    return results

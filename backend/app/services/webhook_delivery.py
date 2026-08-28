"""Webhook delivery — signed delivery with retry/backoff, dead-letter queue, idempotency."""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Webhook, WebhookEvent


def _sign(payload: str, secret: str) -> str:
    """HMAC-SHA256 signature (X-BOS-Signature: sha256=<hex>)."""
    return "sha256=" + hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def deliver_webhook(
    db: AsyncSession,
    company_id: uuid.UUID,
    webhook: Webhook,
    event_type: str,
    payload: dict,
    idempotency_key: str | None = None,
) -> WebhookEvent:
    """Create an execution log entry and deliver the event with retry/backoff."""
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    event = WebhookEvent(
        company_id=company_id,
        webhook_id=webhook.id,
        event_type=event_type,
        payload=payload_json,
        status="pending",
        attempts=0,
        idempotency_key=idempotency_key or uuid.uuid4().hex[:32],
    )
    db.add(event)
    await db.flush()

    headers = {
        "Content-Type": "application/json",
        "X-BOS-Event": event_type,
        "X-BOS-Idempotency-Key": event.idempotency_key,
    }
    if webhook.secret:
        headers["X-BOS-Signature"] = _sign(payload_json, webhook.secret)

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

    # Retry/backoff: schedule next attempt or mark dead
    if event.status == "failed":
        if event.attempts < webhook.retry_max:
            event.next_retry_at = datetime.utcnow() + timedelta(seconds=webhook.retry_backoff_seconds * event.attempts)
        else:
            event.status = "dead"  # dead-letter queue
            event.next_retry_at = None

    await db.flush()
    return event


async def process_retry_queue(db: AsyncSession, company_id: uuid.UUID) -> int:
    """Re-deliver pending events whose next_retry_at has passed."""
    now = datetime.utcnow()
    events = (await db.execute(
        select(WebhookEvent).where(
            WebhookEvent.company_id == company_id,
            WebhookEvent.status == "failed",
            WebhookEvent.next_retry_at.is_not(None),
            WebhookEvent.next_retry_at <= now,
        ).limit(50)
    )).scalars().all()
    delivered = 0
    for event in events:
        webhook = (await db.execute(
            select(Webhook).where(Webhook.id == event.webhook_id)
        )).scalar_one_or_none()
        if not webhook or not webhook.is_active:
            continue
        payload = json.loads(event.payload)
        headers = {
            "Content-Type": "application/json",
            "X-BOS-Event": event.event_type,
            "X-BOS-Idempotency-Key": event.idempotency_key,
        }
        if webhook.secret:
            headers["X-BOS-Signature"] = _sign(event.payload, webhook.secret)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(webhook.url, json=payload, headers=headers)
            event.attempts += 1
            event.last_response_code = resp.status_code
            if resp.status_code < 400:
                event.status = "delivered"
                event.last_error = None
                event.next_retry_at = None
                delivered += 1
            else:
                event.last_error = resp.text[:500]
                if event.attempts >= webhook.retry_max:
                    event.status = "dead"
                    event.next_retry_at = None
                else:
                    event.next_retry_at = now + timedelta(seconds=webhook.retry_backoff_seconds * event.attempts)
        except Exception as exc:  # noqa: BLE001
            event.attempts += 1
            event.last_error = str(exc)[:500]
            if event.attempts >= webhook.retry_max:
                event.status = "dead"
                event.next_retry_at = None
    await db.flush()
    return delivered

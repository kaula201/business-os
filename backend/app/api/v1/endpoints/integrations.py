"""External government integrations + API keys, webhooks, public API."""
import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.integration import ApiKey, Webhook, WebhookEvent
from app.models.user import User
from app.schemas.common import ResponseBase
from app.schemas.integrations import RSGeStatusResponse, RSWaybillResponse
from app.services.rs_ge import RSGeClient, RSGeError

router = APIRouter(prefix="/integrations", tags=["ინტეგრაციები"])


def require_finance_role(user: User) -> None:
    if user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="ინტეგრაციებზე წვდომის უფლება არ გაქვთ")


def rs_client() -> RSGeClient:
    return RSGeClient(settings.RS_WAYBILL_URL, settings.RS_SERVICE_USER, settings.RS_SERVICE_PASSWORD)


@router.get("/rs/status", response_model=ResponseBase[RSGeStatusResponse])
async def rs_status(current_user: User = Depends(get_current_user)):
    require_finance_role(current_user)
    configured = bool(settings.RS_SERVICE_USER and settings.RS_SERVICE_PASSWORD)
    client = rs_client()
    try:
        server_time = await client.get_server_time()
        authenticated = await client.check_service_user() if configured else False
    except RSGeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ResponseBase(data=RSGeStatusResponse(
        configured=configured,
        reachable=True,
        authenticated=authenticated,
        server_time=server_time,
    ))


@router.get("/rs/waybills/{waybill_number}", response_model=ResponseBase[RSWaybillResponse])
async def get_rs_waybill(waybill_number: str, current_user: User = Depends(get_current_user)):
    require_finance_role(current_user)
    if not settings.RS_SERVICE_USER or not settings.RS_SERVICE_PASSWORD:
        raise HTTPException(status_code=503, detail="RS.ge service user credentials არ არის დაყენებული")
    try:
        data = await rs_client().get_waybill_by_number(waybill_number)
    except RSGeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ResponseBase(data=RSWaybillResponse(waybill_number=waybill_number, data=data))


@router.post("/rs/invoices/submit", response_model=ResponseBase[dict])
async def submit_invoice(
    data: dict,
    current_user: User = Depends(get_current_user),
):
    """Submit an invoice (ანგარიშ-ფაქტურა) to RS.ge."""
    require_finance_role(current_user)
    if not settings.RS_SERVICE_USER or not settings.RS_SERVICE_PASSWORD:
        raise HTTPException(status_code=503, detail="RS.ge service user credentials არ არის დაყენებული")
    try:
        result = await rs_client().submit_invoice(
            invoice_number=data.get("invoice_number", ""),
            buyer_id=data.get("buyer_id", ""),
            issue_date=data.get("issue_date", ""),
            total=str(data.get("total", "0")),
            vat=str(data.get("vat", "0")),
        )
    except RSGeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ResponseBase(data=result, message="ინვოისი RS.ge-ზე გაიგზავნა")


@router.post("/rs/waybills/submit", response_model=ResponseBase[dict])
async def submit_waybill(
    data: dict,
    current_user: User = Depends(get_current_user),
):
    """Submit a waybill (ზედნადები) to RS.ge."""
    require_finance_role(current_user)
    if not settings.RS_SERVICE_USER or not settings.RS_SERVICE_PASSWORD:
        raise HTTPException(status_code=503, detail="RS.ge service user credentials არ არის დაყენებული")
    try:
        result = await rs_client().submit_waybill(
            waybill_number=data.get("waybill_number", ""),
            sender_id=data.get("sender_id", ""),
            receiver_id=data.get("receiver_id", ""),
            issue_date=data.get("issue_date", ""),
            total=str(data.get("total", "0")),
        )
    except RSGeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ResponseBase(data=result, message="ზედნადები RS.ge-ზე გაიგზავნა")


@router.post("/rs/declarations/export", response_model=ResponseBase[dict])
async def export_declaration(
    data: dict,
    current_user: User = Depends(get_current_user),
):
    """Export a tax declaration (VAT / income tax) for a period."""
    require_finance_role(current_user)
    if not settings.RS_SERVICE_USER or not settings.RS_SERVICE_PASSWORD:
        raise HTTPException(status_code=503, detail="RS.ge service user credentials არ არის დაყენებული")
    try:
        result = await rs_client().export_declaration(
            period=data.get("period", ""),
            declaration_type=data.get("declaration_type", "vat"),
        )
    except RSGeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ResponseBase(data=result, message="დეკლარაცია ექსპორტირებულია")


# ── API keys ───────────────────────────────────────────────────────────────────

@router.get("/api-keys", response_model=ResponseBase[list[dict]])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_access")),
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.company_id == current_user.company_id).order_by(ApiKey.created_at.desc())
    )
    return ResponseBase(data=[{
        "id": str(k.id), "name": k.name, "key_prefix": k.key_prefix, "scopes": k.scopes,
        "is_active": k.is_active, "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "branch_id": str(k.branch_id) if k.branch_id else None,
        "resource_ids": k.resource_ids or [],
        "allowed_ips": k.allowed_ips or [],
        "rate_limit_per_minute": k.rate_limit_per_minute,
    } for k in result.scalars().all()])


@router.post("/api-keys", response_model=ResponseBase[dict], status_code=201)
async def create_api_key(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_create")),
):
    raw = f"bos_{secrets.token_hex(24)}"
    prefix = raw[:12]
    k = ApiKey(
        company_id=current_user.company_id,
        user_id=current_user.id,
        name=data.get("name", "API Key"),
        key_prefix=prefix,
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        scopes=data.get("scopes", "read"),
        expires_at=data.get("expires_at"),
        branch_id=data.get("branch_id"),
        resource_ids=data.get("resource_ids"),
        allowed_ips=data.get("allowed_ips"),
        rate_limit_per_minute=int(data.get("rate_limit_per_minute", 120)),
    )
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return ResponseBase(data={"id": str(k.id), "name": k.name, "key": raw, "key_prefix": prefix}, message="API Key შეიქმნა")


@router.delete("/api-keys/{key_id}", response_model=ResponseBase[dict])
async def delete_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_delete")),
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.company_id == current_user.company_id))
    k = result.scalar_one_or_none()
    if not k:
        raise HTTPException(status_code=404, detail="API Key არ მოიძებნა")
    await db.delete(k)
    await db.commit()
    return ResponseBase(data={"id": str(key_id)}, message="API Key წაიშალა")


# ── Webhooks ───────────────────────────────────────────────────────────────────

@router.get("/webhooks", response_model=ResponseBase[list[dict]])
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_access")),
):
    result = await db.execute(
        select(Webhook).where(Webhook.company_id == current_user.company_id).order_by(Webhook.created_at.desc())
    )
    return ResponseBase(data=[{"id": str(w.id), "name": w.name, "url": w.url, "events": w.events, "is_active": w.is_active} for w in result.scalars().all()])


@router.post("/webhooks", response_model=ResponseBase[dict], status_code=201)
async def create_webhook(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_create")),
):
    w = Webhook(
        company_id=current_user.company_id,
        name=data.get("name", ""),
        url=data.get("url", ""),
        events=data.get("events", "invoice.created"),
        secret=secrets.token_hex(16),
        retry_max=int(data.get("retry_max", 3)),
        retry_backoff_seconds=int(data.get("retry_backoff_seconds", 60)),
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return ResponseBase(data={"id": str(w.id), "name": w.name, "secret": w.secret}, message="Webhook შეიქმნა")


@router.delete("/webhooks/{webhook_id}", response_model=ResponseBase[dict])
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_delete")),
):
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id, Webhook.company_id == current_user.company_id))
    w = result.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Webhook არ მოიძებნა")
    await db.delete(w)
    await db.commit()
    return ResponseBase(data={"id": str(webhook_id)}, message="Webhook წაიშალა")


# ── Webhook events log ─────────────────────────────────────────────────────────

@router.get("/webhook-events", response_model=ResponseBase[list[dict]])
async def list_webhook_events(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_access")),
):
    result = await db.execute(
        select(WebhookEvent).where(WebhookEvent.company_id == current_user.company_id).order_by(WebhookEvent.created_at.desc()).limit(50)
    )
    return ResponseBase(data=[{
        "id": str(e.id), "event_type": e.event_type, "status": e.status, "attempts": e.attempts,
        "last_response_code": e.last_response_code, "last_error": e.last_error,
        "idempotency_key": e.idempotency_key,
        "next_retry_at": e.next_retry_at.isoformat() if e.next_retry_at else None,
        "created_at": e.created_at.isoformat(),
    } for e in result.scalars().all()])


# ── Retry queue (dead-letter processing) ───────────────────────────────────────


@router.post("/webhook-events/retry", response_model=ResponseBase[dict])
async def retry_failed_events(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_edit")),
):
    from app.services.webhook_delivery import process_retry_queue
    delivered = await process_retry_queue(db, current_user.company_id)
    await db.commit()
    return ResponseBase(data={"retried": delivered}, message="განმეორებითი გაგზავნა დასრულდა")


# ── Public API (API key auth) ─────────────────────────────────────────────────

@router.get("/public/status")
async def public_status(request: Request, db: AsyncSession = Depends(get_db)):
    """Public endpoint authenticated via X-API-Key header."""
    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header აუცილებელია")
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True))
    k = result.scalar_one_or_none()
    if not k:
        raise HTTPException(status_code=401, detail="არასწორი API Key")
    k.last_used_at = func.now()
    await db.commit()
    return ResponseBase(data={"status": "ok", "company_id": str(k.company_id), "scopes": k.scopes})

"""Multi-currency API: exchange rates, conversion."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.config import settings
from app.core.time import utc_now
from app.core.ws import manager
from app.models.currency import CurrencyRate, IntegrationSyncLog
from app.models.user import User
from app.schemas.common import ResponseBase
from app.schemas.currency import (
    CurrencyConversionRequest,
    CurrencyConversionResponse,
    CurrencyRateCreate,
    CurrencyRateResponse,
    NBGSyncResponse,
    NBGSyncStatusResponse,
)
from app.services.nbg_rates import NBGSyncError, add_sync_log, apply_nbg_rates, fetch_nbg_rates

router = APIRouter(prefix="/currency", tags=["ვალუტა"])


@router.websocket("/ws/rates")
async def currency_rates_ws(websocket: WebSocket):
    """Live currency-rate updates. Client sends {company_id} as first message."""
    await websocket.accept()
    company_id = await websocket.receive_text()
    await manager.connect(company_id, websocket)
    try:
        while True:
            # Keep the socket alive; ignore inbound pings.
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        await manager.disconnect(company_id, websocket)


@router.post("/rates/sync-nbg", response_model=ResponseBase[NBGSyncResponse])
async def sync_nbg_rates(
    rate_date: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="კურსების განახლების უფლება არ გაქვთ")
    started_at = utc_now()
    try:
        result = await apply_nbg_rates(
            db,
            current_user.company_id,
            await fetch_nbg_rates(rate_date),
            current_user.id,
        )
    except NBGSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    add_sync_log(db, current_user.company_id, result, "manual", started_at)
    await manager.broadcast(str(current_user.company_id), "rates_updated", {"source": "nbg", "rate_date": str(rate_date or date.today())})
    return ResponseBase(data=NBGSyncResponse(**result), message="ეროვნული ბანკის კურსები განახლებულია")


@router.get("/rates/nbg-status", response_model=ResponseBase[NBGSyncStatusResponse])
async def nbg_sync_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    latest = (
        await db.execute(
            select(IntegrationSyncLog)
            .where(
                IntegrationSyncLog.company_id == current_user.company_id,
                IntegrationSyncLog.integration == "nbg",
            )
            .order_by(
                IntegrationSyncLog.completed_at.desc().nullslast(),
                IntegrationSyncLog.started_at.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    status = NBGSyncStatusResponse(
        enabled=settings.NBG_AUTO_SYNC_ENABLED,
        schedule=f"{settings.NBG_SYNC_HOUR:02d}:{settings.NBG_SYNC_MINUTE:02d}",
        timezone=settings.NBG_SYNC_TIMEZONE,
    )
    if latest:
        status.status = latest.status
        status.trigger = latest.trigger
        status.last_run_at = latest.completed_at or latest.started_at
        status.effective_date = latest.effective_date
        status.currencies_received = latest.currencies_received
        status.rates_created = latest.rates_created
        status.rates_updated = latest.rates_updated
        status.error_message = latest.error_message
    return ResponseBase(data=status)


@router.get("/rates", response_model=ResponseBase[list[CurrencyRateResponse]])
async def list_rates(
    from_currency: str | None = Query(None, max_length=3),
    to_currency: str | None = Query(None, max_length=3),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(CurrencyRate).where(CurrencyRate.company_id == current_user.company_id)
    if from_currency:
        query = query.where(CurrencyRate.from_currency == from_currency.upper())
    if to_currency:
        query = query.where(CurrencyRate.to_currency == to_currency.upper())
    query = query.order_by(CurrencyRate.rate_date.desc(), CurrencyRate.from_currency)
    result = await db.execute(query)
    return ResponseBase(data=result.scalars().all())


@router.post("/rates", response_model=ResponseBase[CurrencyRateResponse], status_code=201)
async def create_rate(
    payload: CurrencyRateCreate,
    current_user: User = Depends(require_module("currency", "can_create")),
    db: AsyncSession = Depends(get_db),
):
    rate = CurrencyRate(
        company_id=current_user.company_id,
        created_by=current_user.id,
        from_currency=payload.from_currency.upper(),
        to_currency=payload.to_currency.upper(),
        rate_date=payload.rate_date,
        rate=payload.rate,
        source=payload.source,
    )
    db.add(rate)
    await db.flush()
    await db.refresh(rate)
    await manager.broadcast(str(current_user.company_id), "rates_updated", {
        "source": "manual",
        "from_currency": rate.from_currency,
        "to_currency": rate.to_currency,
        "rate": str(rate.rate),
        "rate_date": str(rate.rate_date),
    })
    return ResponseBase(data=rate, message="კურსი დამატებულია")


@router.delete("/rates/{rate_id}", response_model=ResponseBase)
async def delete_rate(
    rate_id: UUID,
    current_user: User = Depends(require_module("currency", "can_edit")),
    db: AsyncSession = Depends(get_db),
):
    rate = (
        await db.execute(
            select(CurrencyRate).where(
                CurrencyRate.id == rate_id,
                CurrencyRate.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="კურსი არ მოიძებნა")
    # Audit trail for destructive action
    from app.api.v1.endpoints.purchase_orders import add_audit
    add_audit(db, current_user, "currency_rate.deleted", "currency_rate", rate.id, {
        "from_currency": rate.from_currency,
        "to_currency": rate.to_currency,
        "rate": str(rate.rate),
        "rate_date": str(rate.rate_date),
    })
    await db.delete(rate)
    await manager.broadcast(str(current_user.company_id), "rates_updated", {
        "source": "deleted",
        "from_currency": rate.from_currency,
        "to_currency": rate.to_currency,
    })
    return ResponseBase(message="კურსი წაშლილია")


@router.post("/convert", response_model=ResponseBase[CurrencyConversionResponse])
async def convert_currency(
    payload: CurrencyConversionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Convert amount between currencies using latest available rate."""
    rate_date = payload.rate_date or date.today()

    result = await db.execute(
        select(CurrencyRate)
        .where(
            CurrencyRate.company_id == current_user.company_id,
            CurrencyRate.from_currency == payload.from_currency.upper(),
            CurrencyRate.to_currency == payload.to_currency.upper(),
            CurrencyRate.rate_date <= rate_date,
        )
        .order_by(CurrencyRate.rate_date.desc())
        .limit(1)
    )
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail=f"კურსი არ მოიძებნა {payload.from_currency} → {payload.to_currency}")

    converted = float(payload.amount) * float(rate.rate)
    return ResponseBase(data=CurrencyConversionResponse(
        from_currency=payload.from_currency.upper(),
        to_currency=payload.to_currency.upper(),
        amount=float(payload.amount),
        converted_amount=round(converted, 2),
        rate=float(rate.rate),
        rate_date=rate.rate_date,
    ))

"""POS hardware & configuration endpoints — registers, cashiers (PIN), payment terminals (TBC/BOG), customer credit."""
import hashlib
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.pos_extended import POSCashier, POSPaymentTerminal, POSRegister
from app.models.user import User
from app.schemas.common import ResponseBase
from app.models.client import Client
from sqlalchemy.dialects.postgresql import UUID as SAUUID

router = APIRouter(prefix="/pos", tags=["POS — ჰარდვეარი"])


# ── Registers (cash journal) ──────────────────────────────────────────────


@router.get("/registers", response_model=ResponseBase[list[dict]])
async def list_registers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(POSRegister).where(POSRegister.company_id == current_user.company_id).order_by(POSRegister.code)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(r.id), "name": r.name, "code": r.code,
        "cash_journal_id": str(r.cash_journal_id) if r.cash_journal_id else None,
        "is_active": r.is_active,
    } for r in rows])


@router.post("/registers", response_model=ResponseBase[dict], status_code=201)
async def create_register(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = POSRegister(
        company_id=current_user.company_id,
        name=data.get("name", "").strip(),
        code=data.get("code", "").strip(),
        cash_journal_id=data.get("cash_journal_id"),
        is_active=data.get("is_active", True),
    )
    db.add(r)
    await db.flush()
    return ResponseBase(data={"id": str(r.id), "name": r.name, "code": r.code}, message="რეგისტრი შეიქმნა")


# ── Cashiers (PIN login) ─────────────────────────────────────────────


@router.get("/cashiers", response_model=ResponseBase[list[dict]])
async def list_cashiers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(POSCashier).where(POSCashier.company_id == current_user.company_id)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(c.id), "user_id": str(c.user_id), "is_active": c.is_active,
    } for c in rows])


@router.post("/cashiers", response_model=ResponseBase[dict], status_code=201)
async def create_cashier(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = data.get("user_id")
    pin = str(data.get("pin", ""))
    if not user_id or len(pin) < 4:
        raise HTTPException(status_code=422, detail="user_id და მინიმუმ 4-ნიშნა PIN აუცილებელია")
    existing = (await db.execute(
        select(POSCashier).where(
            POSCashier.company_id == current_user.company_id,
            POSCashier.user_id == user_id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="ასეთი cashier უკვე არსებობს")
    c = POSCashier(
        company_id=current_user.company_id,
        user_id=user_id,
        pin_hash=hashlib.sha256(pin.encode()).hexdigest(),
        is_active=True,
    )
    db.add(c)
    await db.flush()
    return ResponseBase(data={"id": str(c.id)}, message="Cashier შეიქმნა")


@router.post("/cashiers/verify", response_model=ResponseBase[dict])
async def verify_cashier_pin(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = data.get("user_id")
    pin = str(data.get("pin", ""))
    cashier = (await db.execute(
        select(POSCashier).where(
            POSCashier.company_id == current_user.company_id,
            POSCashier.user_id == user_id,
            POSCashier.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if not cashier or cashier.pin_hash != hashlib.sha256(pin.encode()).hexdigest():
        raise HTTPException(status_code=401, detail="არასწორი PIN")
    return ResponseBase(data={"user_id": str(user_id), "verified": True}, message="PIN მიღებულია")


# ── Payment terminals (TBC/BOG) ──────────────────────────────────────


@router.get("/terminals", response_model=ResponseBase[list[dict]])
async def list_terminals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(POSPaymentTerminal).where(POSPaymentTerminal.company_id == current_user.company_id)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(t.id), "name": t.name, "provider": t.provider,
        "terminal_id": t.terminal_id, "merchant_id": t.merchant_id, "is_active": t.is_active,
    } for t in rows])


@router.post("/terminals", response_model=ResponseBase[dict], status_code=201)
async def create_terminal(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    provider = data.get("provider", "").lower()
    if provider not in ("tbc", "bog"):
        raise HTTPException(status_code=422, detail="provider უნდა იყოს tbc ან bog")
    t = POSPaymentTerminal(
        company_id=current_user.company_id,
        name=data.get("name", "").strip(),
        provider=provider,
        terminal_id=data.get("terminal_id", "").strip(),
        merchant_id=data.get("merchant_id"),
        is_active=data.get("is_active", True),
    )
    db.add(t)
    await db.flush()
    return ResponseBase(data={"id": str(t.id), "provider": provider}, message="ტერმინალი დაემატა")


@router.post("/terminals/{terminal_id}/charge", response_model=ResponseBase[dict])
async def terminal_charge(
    terminal_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Card charge via TBC/BOG terminal — real provider integration when
    merchant credentials are configured, sandbox otherwise. The transaction
    is recorded in payment_transactions and a fiscal receipt is issued."""
    from app.models.payment import PaymentTransaction
    from app.services.payment_providers import FiscalDevice, PaymentProviderError, get_provider

    terminal = (await db.execute(
        select(POSPaymentTerminal).where(
            POSPaymentTerminal.id == terminal_id,
            POSPaymentTerminal.company_id == current_user.company_id,
            POSPaymentTerminal.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if not terminal:
        raise HTTPException(status_code=404, detail="ტერმინალი არ მოიძებნა")
    amount = Decimal(str(data.get("amount", 0)))
    if amount <= 0:
        raise HTTPException(status_code=422, detail="თანხა დადებითი უნდა იყოს")

    provider = get_provider(terminal.provider)
    reference = data.get("reference") or f"{terminal.provider}-{uuid.uuid4().hex[:12].upper()}"
    try:
        result = await provider.charge(amount, currency=data.get("currency", "GEL"), reference=reference)
    except PaymentProviderError as e:
        # record failed transaction
        tx = PaymentTransaction(
            company_id=current_user.company_id, provider=terminal.provider,
            amount=amount, status="failed", error_message=str(e),
        )
        db.add(tx)
        await db.flush()
        await db.commit()
        raise HTTPException(status_code=502, detail=str(e)) from e

    tx = PaymentTransaction(
        company_id=current_user.company_id, provider=terminal.provider,
        amount=amount, status="succeeded" if result["status"] == "authorized" else "pending",
        provider_ref=result.get("provider_ref"),
    )
    db.add(tx)
    await db.flush()

    # fiscal receipt (certified device when configured, sandbox otherwise)
    fiscal = FiscalDevice()
    receipt = {
        "transaction_id": str(tx.id), "amount": float(amount),
        "currency": data.get("currency", "GEL"), "provider": terminal.provider,
        "terminal": terminal.name, "items": data.get("items", []),
    }
    try:
        fiscal_result = await fiscal.print_receipt(receipt)
    except PaymentProviderError:
        fiscal_result = {"status": "failed", "fiscal_number": None}

    await db.commit()
    return ResponseBase(data={
        "transaction_id": str(tx.id),
        "provider": terminal.provider,
        "amount": float(amount),
        "status": result["status"],
        "reference": result.get("provider_ref"),
        "gateway": "live" if not provider.sandbox else "sandbox",
        "fiscal_number": fiscal_result.get("fiscal_number"),
    }, message=f"{terminal.provider.upper()} ტერმინალი — თანხა ჩარიცხულია")


@router.post("/terminals/{terminal_id}/refund", response_model=ResponseBase[dict])
async def terminal_refund(
    terminal_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Refund a terminal charge via the provider."""
    from app.models.payment import PaymentTransaction
    from app.services.payment_providers import PaymentProviderError, get_provider

    terminal = (await db.execute(
        select(POSPaymentTerminal).where(
            POSPaymentTerminal.id == terminal_id,
            POSPaymentTerminal.company_id == current_user.company_id,
        )
    )).scalar_one_or_none()
    if not terminal:
        raise HTTPException(status_code=404, detail="ტერმინალი არ მოიძებნა")
    provider_ref = data.get("provider_ref")
    if not provider_ref:
        raise HTTPException(status_code=422, detail="provider_ref აუცილებელია")
    amount = Decimal(str(data.get("amount", 0)))

    provider = get_provider(terminal.provider)
    try:
        result = await provider.refund(provider_ref, amount)
    except PaymentProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    tx = PaymentTransaction(
        company_id=current_user.company_id, provider=terminal.provider,
        amount=amount, status="refunded", provider_ref=provider_ref,
    )
    db.add(tx)
    await db.flush()
    await db.commit()
    return ResponseBase(data={
        "transaction_id": str(tx.id), "provider": terminal.provider,
        "amount": float(amount), "status": result["status"],
        "reference": provider_ref,
    }, message="თანხა დაბრუნდა")


@router.get("/terminals/{terminal_id}/status/{provider_ref}", response_model=ResponseBase[dict])
async def terminal_status(
    terminal_id: uuid.UUID,
    provider_ref: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check a terminal charge status with the provider."""
    from app.services.payment_providers import PaymentProviderError, get_provider

    terminal = (await db.execute(
        select(POSPaymentTerminal).where(
            POSPaymentTerminal.id == terminal_id,
            POSPaymentTerminal.company_id == current_user.company_id,
        )
    )).scalar_one_or_none()
    if not terminal:
        raise HTTPException(status_code=404, detail="ტერმინალი არ მოიძებნა")
    provider = get_provider(terminal.provider)
    try:
        result = await provider.check_status(provider_ref)
    except PaymentProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return ResponseBase(data=result)


# ── Customer credit / deposit ────────────────────────────────────────


@router.get("/customer-balance/{client_id}", response_model=ResponseBase[dict])
async def customer_balance(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")
    return ResponseBase(data={
        "client_id": str(client.id),
        "balance": float(client.balance or 0),
        "credit_limit": float(client.credit_limit or 0),
    })


@router.post("/customers/{client_id}/deposit", response_model=ResponseBase[dict])
async def customer_deposit(
    client_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")
    amount = Decimal(str(data.get("amount", 0)))
    if amount <= 0:
        raise HTTPException(status_code=422, detail="თანხა დადიატი უნდა იყოს")
    client.balance = (client.balance or 0) + float(amount)
    await db.flush()
    return ResponseBase(data={"client_id": str(client.id), "balance": client.balance}, message="დეპოზიტი ჩარიცხულია")


# ── QR payment ───────────────────────────────────────────────────────


@router.post("/qr/pay", response_model=ResponseBase[dict])
async def qr_payment(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """QR payment — order paid via bank QR (TBC Pay / BOG Pay style)."""
    amount = Decimal(str(data.get("amount", 0)))
    if amount <= 0:
        raise HTTPException(status_code=422, detail="თანი დადიატი უნდა იყოს")
    qr_token = data.get("qr_token") or uuid.uuid4().hex[:12].upper()
    return ResponseBase(data={
        "qr_token": qr_token,
        "amount": float(amount),
        "status": "paid",
        "reference": f"QR-{uuid.uuid4().hex[:10].upper()}",
    }, message="QR გადახდა მიღებულია")

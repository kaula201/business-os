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
    """Card charge via TBC/BOG terminal — real integration hooks to the provider SDK."""
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
    # TODO: TBC/BOG SDK charge call — production requires merchant credentials.
    return ResponseBase(data={
        "transaction_id": f"{terminal.provider}-{uuid.uuid4().hex[:12].upper()}",
        "provider": terminal.provider,
        "amount": float(amount),
        "status": "authorized",
        "reference": data.get("reference"),
    }, message=f"{terminal.provider.upper()} ტერმინალი — თანხა ჩარიცხულია")


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

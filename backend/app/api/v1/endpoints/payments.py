"""Payment gateway endpoints — create, list, confirm, refund."""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.payment import PaymentTransaction
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/payments", tags=["გადახდები"])


@router.get("/", response_model=ResponseBase[list[dict]])
async def list_payments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("payments", "can_access")),
):
    result = await db.execute(
        select(PaymentTransaction).where(PaymentTransaction.company_id == current_user.company_id).order_by(PaymentTransaction.created_at.desc()).limit(100)
    )
    return ResponseBase(data=[{
        "id": str(p.id), "provider": p.provider, "amount": float(p.amount), "currency": p.currency,
        "status": p.status, "provider_ref": p.provider_ref, "created_at": p.created_at.isoformat(),
    } for p in result.scalars().all()])


@router.post("/", response_model=ResponseBase[dict], status_code=201)
async def create_payment(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("payments", "can_create")),
):
    """Create a payment transaction. In sandbox mode returns a mock provider_ref."""
    try:
        amount = Decimal(str(data.get("amount", "0")))
    except Exception:
        raise HTTPException(status_code=422, detail="თანხა არასწორია")
    if amount <= 0:
        raise HTTPException(status_code=422, detail="თანხა უნდა იყოს დადებითი")

    provider = data.get("provider", "cash")
    p = PaymentTransaction(
        company_id=current_user.company_id,
        order_id=data.get("order_id"),
        invoice_id=data.get("invoice_id"),
        provider=provider,
        amount=amount,
        currency=data.get("currency", "GEL"),
        status="succeeded" if provider == "cash" else "pending",
        provider_ref=f"{provider}_{uuid.uuid4().hex[:12]}" if provider != "cash" else None,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return ResponseBase(data={
        "id": str(p.id), "provider": p.provider, "amount": float(p.amount),
        "status": p.status, "provider_ref": p.provider_ref,
    }, message="გადახდა შეიქმნა")


@router.post("/{payment_id}/confirm", response_model=ResponseBase[dict])
async def confirm_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("payments", "can_edit")),
):
    result = await db.execute(
        select(PaymentTransaction).where(PaymentTransaction.id == payment_id, PaymentTransaction.company_id == current_user.company_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="გადახდა არ მოიძებნა")
    if p.status == "succeeded":
        raise HTTPException(status_code=400, detail="გადახდა უკვე დადასტურებულია")
    p.status = "succeeded"
    await db.commit()
    return ResponseBase(data={"id": str(p.id), "status": p.status}, message="გადახდა დადასტურდა")


@router.post("/{payment_id}/refund", response_model=ResponseBase[dict])
async def refund_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("payments", "can_edit")),
):
    result = await db.execute(
        select(PaymentTransaction).where(PaymentTransaction.id == payment_id, PaymentTransaction.company_id == current_user.company_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="გადახდა არ მოიძებნა")
    if p.status != "succeeded":
        raise HTTPException(status_code=400, detail="მხოლოდ დადასტურებული გადახდის დაბრუნება შეიძლება")
    p.status = "refunded"
    await db.commit()
    return ResponseBase(data={"id": str(p.id), "status": p.status}, message="გადახდა დაბრუნდა")

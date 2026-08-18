"""Tenders: competitive procurement with supplier bids and award."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.product import Product
from app.models.purchase import Supplier
from app.models.tender import Tender, TenderBid, TenderBidLine, TenderLine
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/procurement/tenders", tags=["Procurement — ტენდერები"])


class TenderLineIn(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(..., gt=0)
    expected_price: Decimal | None = None


class TenderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    required_date: date | None = None
    budget_amount: Decimal | None = None
    currency: str = "GEL"
    lines: list[TenderLineIn] = Field(default_factory=list)


class TenderBidIn(BaseModel):
    supplier_id: UUID
    delivery_days: int | None = None
    notes: str | None = None
    lines: list[dict] = Field(default_factory=list)  # [{tender_line_id, unit_price, currency}]


async def _require_supplier(db: AsyncSession, company_id: UUID, supplier_id: UUID) -> Supplier:
    s = (await db.execute(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.company_id == company_id)
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="მომწოდებელი არ მოიძებნა")
    return s


async def _require_product(db: AsyncSession, company_id: UUID, product_id: UUID) -> Product:
    p = (await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == company_id)
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")
    return p


def _tender_row(t: Tender) -> dict:
    # Avoid lazy-loading relationships in async context; counts are computed
    # only from already-loaded collections (selectinload), else 0.
    lines_count = len(t.lines) if "lines" in t.__dict__ else 0
    bids_count = len(t.bids) if "bids" in t.__dict__ else 0
    lines = []
    if "lines" in t.__dict__:
        lines = [{"id": str(l.id), "product_id": str(l.product_id), "quantity": float(l.quantity),
                  "expected_price": float(l.expected_price) if l.expected_price else None} for l in t.lines]
    return {
        "id": str(t.id), "tender_number": t.tender_number, "title": t.title,
        "description": t.description, "status": t.status, "required_date": str(t.required_date) if t.required_date else None,
        "budget_amount": float(t.budget_amount) if t.budget_amount else None, "currency": t.currency,
        "awarded_supplier_id": str(t.awarded_supplier_id) if t.awarded_supplier_id else None,
        "lines_count": lines_count, "bids_count": bids_count, "lines": lines,
        "created_at": t.created_at.isoformat(),
    }


@router.post("", response_model=ResponseBase[dict], status_code=201)
async def create_tender(
    payload: TenderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    company_id = current_user.company_id
    if not payload.lines:
        raise HTTPException(status_code=422, detail="ტენდერი ცარიელია")
    for line in payload.lines:
        await _require_product(db, company_id, line.product_id)
    count = await db.scalar(select(func.count(Tender.id)).where(Tender.company_id == company_id))
    tender = Tender(
        company_id=company_id,
        tender_number=f"TND-{datetime.now():%Y%m%d}-{int(count or 0) + 1:04d}",
        title=payload.title, description=payload.description, status="draft",
        required_date=payload.required_date, budget_amount=payload.budget_amount,
        currency=payload.currency, created_by=current_user.id,
    )
    db.add(tender)
    await db.flush()
    for line in payload.lines:
        db.add(TenderLine(tender_id=tender.id, product_id=line.product_id, quantity=line.quantity, expected_price=line.expected_price))
    await db.flush()
    return ResponseBase(data={
        "id": str(tender.id), "tender_number": tender.tender_number, "title": tender.title,
        "description": tender.description, "status": tender.status,
        "required_date": str(tender.required_date) if tender.required_date else None,
        "budget_amount": float(tender.budget_amount) if tender.budget_amount else None,
        "currency": tender.currency, "awarded_supplier_id": None,
        "lines_count": len(payload.lines), "bids_count": 0,
        "created_at": tender.created_at.isoformat(),
    }, message="ტენდერი შეიქმნა")


@router.get("", response_model=ResponseBase[list[dict]])
async def list_tenders(
    status: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_view")),
):
    filters = [Tender.company_id == current_user.company_id]
    if status:
        filters.append(Tender.status == status)
    rows = (await db.execute(
        select(Tender).where(*filters)
        .options(selectinload(Tender.lines), selectinload(Tender.bids))
        .order_by(Tender.created_at.desc()).limit(limit)
    )).scalars().all()
    return ResponseBase(data=[_tender_row(t) for t in rows])


@router.post("/{tender_id}/publish", response_model=ResponseBase[dict])
async def publish_tender(
    tender_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    tender = (await db.execute(select(Tender).where(
        Tender.id == tender_id, Tender.company_id == current_user.company_id
    ))).scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="ტენდერი არ მოიძებნა")
    if tender.status != "draft":
        raise HTTPException(status_code=409, detail="მხოლოდ draft ტენდერი შეიძლება გამოქვეყნდეს")
    tender.status = "bidding"
    await db.flush()
    return ResponseBase(data=_tender_row(tender), message="ტენდერი გამოქვეყნდა")


@router.post("/{tender_id}/bids", response_model=ResponseBase[dict], status_code=201)
async def submit_bid(
    tender_id: UUID,
    payload: TenderBidIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    company_id = current_user.company_id
    tender = (await db.execute(select(Tender).where(
        Tender.id == tender_id, Tender.company_id == company_id
    ))).scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="ტენდერი არ მოიძებნა")
    if tender.status not in ("bidding", "evaluating"):
        raise HTTPException(status_code=409, detail="ტენდერი არ იღებს შეთავაზებებს")
    await _require_supplier(db, company_id, payload.supplier_id)
    existing = (await db.execute(select(TenderBid).where(
        TenderBid.tender_id == tender_id, TenderBid.supplier_id == payload.supplier_id
    ))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="ამ მომწოდებლის შეთავაზება უკვე არსებობს")

    total = Decimal("0")
    for line in payload.lines:
        unit_price = Decimal(str(line.get("unit_price", 0)))
        tender_line = (await db.execute(select(TenderLine).where(
            TenderLine.id == line.get("tender_line_id"), TenderLine.tender_id == tender_id
        ))).scalar_one_or_none()
        if not tender_line:
            raise HTTPException(status_code=422, detail="ტენდერის ხაზი არ მოიძებნა")
        total += unit_price * tender_line.quantity

    bid = TenderBid(
        tender_id=tender_id, supplier_id=payload.supplier_id, status="submitted",
        total_amount=total, currency=tender.currency, delivery_days=payload.delivery_days, notes=payload.notes,
    )
    db.add(bid)
    await db.flush()
    for line in payload.lines:
        db.add(TenderBidLine(
            bid_id=bid.id, tender_line_id=line.get("tender_line_id"),
            product_id=line.get("product_id"), unit_price=Decimal(str(line.get("unit_price", 0))),
            currency=line.get("currency", tender.currency), delivery_days=line.get("delivery_days"),
        ))
    await db.flush()
    return ResponseBase(data={"id": str(bid.id), "tender_id": str(tender_id), "supplier_id": str(payload.supplier_id),
                              "total_amount": float(total), "status": bid.status}, message="შეთავაზება შეიტანა")


@router.get("/{tender_id}/comparison", response_model=ResponseBase[list[dict]])
async def tender_comparison(
    tender_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_view")),
):
    tender = (await db.execute(select(Tender).where(
        Tender.id == tender_id, Tender.company_id == current_user.company_id
    ))).scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="ტენდერი არ მოიძებნა")
    bids = (await db.execute(
        select(TenderBid).where(TenderBid.tender_id == tender_id)
        .options(selectinload(TenderBid.supplier))
        .order_by(TenderBid.total_amount.asc())
    )).scalars().all()
    return ResponseBase(data=[{
        "bid_id": str(b.id), "supplier_id": str(b.supplier_id), "supplier_name": b.supplier.name,
        "total_amount": float(b.total_amount), "currency": b.currency, "delivery_days": b.delivery_days,
        "status": b.status, "created_at": b.created_at.isoformat(),
    } for b in bids])


@router.post("/{tender_id}/award", response_model=ResponseBase[dict])
async def award_tender(
    tender_id: UUID,
    supplier_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    company_id = current_user.company_id
    tender = (await db.execute(select(Tender).where(
        Tender.id == tender_id, Tender.company_id == company_id
    ))).scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="ტენდერი არ მოიძებნა")
    if tender.status not in ("bidding", "evaluating"):
        raise HTTPException(status_code=409, detail="ტენდერი ვერ გადაეცემა ამ სტატუსში")
    await _require_supplier(db, company_id, supplier_id)
    bid = (await db.execute(select(TenderBid).where(
        TenderBid.tender_id == tender_id, TenderBid.supplier_id == supplier_id
    ))).scalar_one_or_none()
    if not bid:
        raise HTTPException(status_code=422, detail="მომწოდებელს შეთავაზება არ აქვს")
    tender.status = "awarded"
    tender.awarded_supplier_id = supplier_id
    bid.status = "accepted"
    await db.flush()
    return ResponseBase(data=_tender_row(tender), message="ტენდერი გადაეცა მომწოდებელს")

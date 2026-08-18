"""Procurement: RFQ, comparison, vendor pricelists, blanket orders, scorecards, auto-replenishment."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.product import Product
from app.models.procurement import (
    BlanketOrder,
    BlanketOrderLine,
    RFQ,
    RFQLine,
    RFQResponse,
    RFQResponseLine,
    SupplierPriceList,
    SupplierPriceHistory,
    SupplierScorecard,
)
from app.models.purchase import PurchaseOrder, PurchaseOrderItem, Supplier
from app.models.warehouse import InventoryBalance
from app.models.wms_ops import ReplenishmentRule
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/procurement", tags=["Procurement — შესყიდვები"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class RFQLineIn(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(..., gt=0)
    expected_price: Decimal | None = None


class RFQCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    required_date: date | None = None
    notes: str | None = None
    lines: list[RFQLineIn] = Field(default_factory=list)


class RFQResponseIn(BaseModel):
    supplier_id: UUID
    delivery_days: int | None = None
    notes: str | None = None
    lines: list[dict] = Field(default_factory=list)  # [{rfq_line_id, unit_price, currency}]


class PriceListIn(BaseModel):
    supplier_id: UUID
    product_id: UUID
    price: Decimal = Field(..., gt=0)
    currency: str = "GEL"
    valid_from: date | None = None
    valid_to: date | None = None


class BlanketOrderIn(BaseModel):
    supplier_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None
    lines: list[dict] = Field(default_factory=list)  # [{product_id, quantity, unit_price, currency}]


class ScorecardIn(BaseModel):
    supplier_id: UUID
    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    on_time_delivery_rate: Decimal | None = None
    quality_rate: Decimal | None = None
    price_index: Decimal | None = None
    notes: str | None = None


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


# ── RFQ ──────────────────────────────────────────────────────────────────────

@router.post("/rfqs", response_model=ResponseBase[dict], status_code=201)
async def create_rfq(
    payload: RFQCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    company_id = current_user.company_id
    if not payload.lines:
        raise HTTPException(status_code=422, detail="RFQ ცარიელია")
    count = await db.scalar(select(func.count(RFQ.id)).where(RFQ.company_id == company_id))
    rfq = RFQ(
        company_id=company_id,
        rfq_number=f"RFQ-{datetime.now():%Y%m%d}-{int(count or 0) + 1:04d}",
        title=payload.title,
        status="draft",
        required_date=payload.required_date,
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(rfq)
    await db.flush()
    for line in payload.lines:
        await _require_product(db, company_id, line.product_id)
        db.add(RFQLine(rfq_id=rfq.id, product_id=line.product_id, quantity=line.quantity, expected_price=line.expected_price))
    await db.flush()
    return ResponseBase(data={"id": str(rfq.id), "rfq_number": rfq.rfq_number}, message="RFQ შექმნილია")


@router.get("/rfqs", response_model=ResponseBase[list[dict]])
async def list_rfqs(
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_access")),
):
    query = select(RFQ).where(RFQ.company_id == current_user.company_id)
    if status:
        query = query.where(RFQ.status == status)
    query = query.order_by(RFQ.created_at.desc()).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    result = []
    for r in rows:
        lines = (await db.execute(select(RFQLine).where(RFQLine.rfq_id == r.id))).scalars().all()
        responses = (await db.execute(select(RFQResponse).where(RFQResponse.rfq_id == r.id))).scalars().all()
        result.append({
            "id": str(r.id), "rfq_number": r.rfq_number, "title": r.title, "status": r.status,
            "required_date": r.required_date.isoformat() if r.required_date else None,
            "awarded_supplier_id": str(r.awarded_supplier_id) if r.awarded_supplier_id else None,
            "created_at": r.created_at.isoformat(),
            "lines": [{"id": str(l.id), "product_id": str(l.product_id), "quantity": float(l.quantity),
                       "expected_price": float(l.expected_price) if l.expected_price else None} for l in lines],
            "responses_count": len(responses),
        })
    return ResponseBase(data=result)


@router.post("/rfqs/{rfq_id}/responses", response_model=ResponseBase[dict], status_code=201)
async def submit_rfq_response(
    rfq_id: UUID,
    payload: RFQResponseIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    company_id = current_user.company_id
    rfq = (await db.execute(select(RFQ).where(RFQ.id == rfq_id, RFQ.company_id == company_id))).scalar_one_or_none()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ არ მოიძებნა")
    if rfq.status in ("awarded", "cancelled"):
        raise HTTPException(status_code=409, detail="RFQ დახურულია")
    await _require_supplier(db, company_id, payload.supplier_id)
    response = RFQResponse(
        rfq_id=rfq.id, supplier_id=payload.supplier_id,
        delivery_days=payload.delivery_days, notes=payload.notes,
    )
    db.add(response)
    await db.flush()
    for line in payload.lines:
        rfq_line_id = UUID(line["rfq_line_id"])
        unit_price = Decimal(str(line["unit_price"]))
        currency = line.get("currency", "GEL")
        rfq_line = (await db.execute(select(RFQLine).where(RFQLine.id == rfq_line_id, RFQLine.rfq_id == rfq.id))).scalar_one_or_none()
        if not rfq_line:
            raise HTTPException(status_code=404, detail="RFQ ხაზი არ მოიძებნა")
        db.add(RFQResponseLine(
            response_id=response.id, rfq_line_id=rfq_line.id,
            product_id=rfq_line.product_id, unit_price=unit_price, currency=currency,
            delivery_days=payload.delivery_days,
        ))
    rfq.status = "receiving"
    await db.flush()
    return ResponseBase(data={"id": str(response.id)}, message="შეთავაზება მიღებულია")


@router.get("/rfqs/{rfq_id}/comparison", response_model=ResponseBase[list[dict]])
async def rfq_comparison(
    rfq_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_access")),
):
    """Compare vendor offers line by line — best price per product."""
    company_id = current_user.company_id
    rfq = (await db.execute(select(RFQ).where(RFQ.id == rfq_id, RFQ.company_id == company_id))).scalar_one_or_none()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ არ მოიძებნა")
    lines = (await db.execute(select(RFQLine).where(RFQLine.rfq_id == rfq.id))).scalars().all()
    responses = (await db.execute(select(RFQResponse).where(RFQResponse.rfq_id == rfq.id))).scalars().all()
    result = []
    for line in lines:
        offers = []
        for resp in responses:
            resp_lines = (await db.execute(
                select(RFQResponseLine).where(RFQResponseLine.response_id == resp.id, RFQResponseLine.rfq_line_id == line.id)
            )).scalars().all()
            for rl in resp_lines:
                supplier = (await db.execute(select(Supplier).where(Supplier.id == resp.supplier_id))).scalar_one_or_none()
                offers.append({
                    "supplier_id": str(resp.supplier_id),
                    "supplier_name": supplier.name if supplier else "—",
                    "unit_price": float(rl.unit_price),
                    "currency": rl.currency,
                    "delivery_days": rl.delivery_days,
                    "total": float(rl.unit_price * line.quantity),
                })
        offers.sort(key=lambda o: o["unit_price"])
        result.append({
            "rfq_line_id": str(line.id),
            "product_id": str(line.product_id),
            "quantity": float(line.quantity),
            "expected_price": float(line.expected_price) if line.expected_price else None,
            "offers": offers,
            "best_offer": offers[0] if offers else None,
        })
    return ResponseBase(data=result)


@router.post("/rfqs/{rfq_id}/award", response_model=ResponseBase[dict])
async def award_rfq(
    rfq_id: UUID,
    supplier_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    company_id = current_user.company_id
    rfq = (await db.execute(select(RFQ).where(RFQ.id == rfq_id, RFQ.company_id == company_id))).scalar_one_or_none()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ არ მოიძებნა")
    await _require_supplier(db, company_id, supplier_id)
    rfq.awarded_supplier_id = supplier_id
    rfq.status = "awarded"
    await db.execute(
        update(RFQResponse).where(
            RFQResponse.rfq_id == rfq.id, RFQResponse.supplier_id == supplier_id
        ).values(status="accepted")
    )
    await db.flush()
    return ResponseBase(data={"id": str(rfq.id)}, message="RFQ გადაეცა მომწოდებელს")


# ── Vendor pricelist ─────────────────────────────────────────────────────────

@router.post("/price-lists", response_model=ResponseBase[dict], status_code=201)
async def upsert_price_list(
    payload: PriceListIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    company_id = current_user.company_id
    await _require_supplier(db, company_id, payload.supplier_id)
    await _require_product(db, company_id, payload.product_id)
    existing = (await db.execute(
        select(SupplierPriceList).where(
            SupplierPriceList.company_id == company_id,
            SupplierPriceList.supplier_id == payload.supplier_id,
            SupplierPriceList.product_id == payload.product_id,
        )
    )).scalar_one_or_none()
    if existing:
        # Record a price-history snapshot whenever the price actually changes.
        if existing.price != payload.price:
            db.add(SupplierPriceHistory(
                company_id=company_id, supplier_id=payload.supplier_id, product_id=payload.product_id,
                price=existing.price, currency=existing.currency, changed_by=current_user.id,
            ))
        existing.price = payload.price
        existing.currency = payload.currency
        existing.valid_from = payload.valid_from
        existing.valid_to = payload.valid_to
        existing.is_active = True
        await db.flush()
        return ResponseBase(data={"id": str(existing.id)}, message="ფასი განახლებულია")
    pl = SupplierPriceList(
        company_id=company_id, supplier_id=payload.supplier_id, product_id=payload.product_id,
        price=payload.price, currency=payload.currency,
        valid_from=payload.valid_from, valid_to=payload.valid_to,
    )
    db.add(pl)
    await db.flush()
    return ResponseBase(data={"id": str(pl.id)}, message="ფასი დამატებულია")


@router.get("/price-lists", response_model=ResponseBase[list[dict]])
async def list_price_lists(
    supplier_id: UUID | None = None,
    product_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_access")),
):
    query = select(SupplierPriceList).where(SupplierPriceList.company_id == current_user.company_id)
    if supplier_id:
        query = query.where(SupplierPriceList.supplier_id == supplier_id)
    if product_id:
        query = query.where(SupplierPriceList.product_id == product_id)
    rows = (await db.execute(query)).scalars().all()
    result = []
    for p in rows:
        supplier = (await db.execute(select(Supplier).where(Supplier.id == p.supplier_id))).scalar_one_or_none()
        product = (await db.execute(select(Product).where(Product.id == p.product_id))).scalar_one_or_none()
        result.append({
            "id": str(p.id), "supplier_id": str(p.supplier_id),
            "supplier_name": supplier.name if supplier else "—",
            "product_id": str(p.product_id), "product_name": product.name if product else "—",
            "price": float(p.price), "currency": p.currency,
            "valid_from": p.valid_from.isoformat() if p.valid_from else None,
            "valid_to": p.valid_to.isoformat() if p.valid_to else None,
            "is_active": p.is_active,
        })
    return ResponseBase(data=result)


@router.get("/price-trend", response_model=ResponseBase[list[dict]])
async def price_trend(
    supplier_id: UUID | None = None,
    product_id: UUID | None = None,
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_access")),
):
    """Vendor price history — chronological snapshots for trend analysis."""
    query = select(SupplierPriceHistory).where(SupplierPriceHistory.company_id == current_user.company_id)
    if supplier_id:
        query = query.where(SupplierPriceHistory.supplier_id == supplier_id)
    if product_id:
        query = query.where(SupplierPriceHistory.product_id == product_id)
    query = query.order_by(SupplierPriceHistory.changed_at.desc()).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    result = []
    for h in rows:
        supplier = (await db.execute(select(Supplier).where(Supplier.id == h.supplier_id))).scalar_one_or_none()
        product = (await db.execute(select(Product).where(Product.id == h.product_id))).scalar_one_or_none()
        result.append({
            "id": str(h.id), "supplier_id": str(h.supplier_id),
            "supplier_name": supplier.name if supplier else "—",
            "product_id": str(h.product_id), "product_name": product.name if product else "—",
            "price": float(h.price), "currency": h.currency,
            "changed_at": h.changed_at.isoformat(),
        })
    return ResponseBase(data=result)


# ── Blanket orders ────────────────────────────────────────────────────────────

@router.post("/blanket-orders", response_model=ResponseBase[dict], status_code=201)
async def create_blanket_order(
    payload: BlanketOrderIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    company_id = current_user.company_id
    await _require_supplier(db, company_id, payload.supplier_id)
    if not payload.lines:
        raise HTTPException(status_code=422, detail="ჩარჩო შეთანხმება ცარიელია")
    count = await db.scalar(select(func.count(BlanketOrder.id)).where(BlanketOrder.company_id == company_id))
    bo = BlanketOrder(
        company_id=company_id, supplier_id=payload.supplier_id,
        blanket_number=f"BO-{datetime.now():%Y%m%d}-{int(count or 0) + 1:04d}",
        title=payload.title, status="draft",
        start_date=payload.start_date, end_date=payload.end_date, notes=payload.notes,
    )
    db.add(bo)
    await db.flush()
    for line in payload.lines:
        await _require_product(db, company_id, UUID(line["product_id"]))
        db.add(BlanketOrderLine(
            blanket_order_id=bo.id, product_id=UUID(line["product_id"]),
            quantity=Decimal(str(line["quantity"])), unit_price=Decimal(str(line["unit_price"])),
            currency=line.get("currency", "GEL"),
        ))
    await db.flush()
    return ResponseBase(data={"id": str(bo.id), "blanket_number": bo.blanket_number}, message="ჩარჩო შეთანხმება შექმნილია")


@router.get("/blanket-orders", response_model=ResponseBase[list[dict]])
async def list_blanket_orders(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_access")),
):
    query = select(BlanketOrder).where(BlanketOrder.company_id == current_user.company_id)
    if status:
        query = query.where(BlanketOrder.status == status)
    rows = (await db.execute(query)).scalars().all()
    result = []
    for b in rows:
        supplier = (await db.execute(select(Supplier).where(Supplier.id == b.supplier_id))).scalar_one_or_none()
        lines = (await db.execute(select(BlanketOrderLine).where(BlanketOrderLine.blanket_order_id == b.id))).scalars().all()
        result.append({
            "id": str(b.id), "blanket_number": b.blanket_number, "title": b.title, "status": b.status,
            "supplier_id": str(b.supplier_id), "supplier_name": supplier.name if supplier else "—",
            "start_date": b.start_date.isoformat() if b.start_date else None,
            "end_date": b.end_date.isoformat() if b.end_date else None,
            "lines": [{"id": str(l.id), "product_id": str(l.product_id), "quantity": float(l.quantity),
                       "used_quantity": float(l.used_quantity), "unit_price": float(l.unit_price),
                       "currency": l.currency} for l in lines],
        })
    return ResponseBase(data=result)


@router.post("/blanket-orders/{blanket_id}/activate", response_model=ResponseBase[dict])
async def activate_blanket_order(
    blanket_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    bo = (await db.execute(
        select(BlanketOrder).where(BlanketOrder.id == blanket_id, BlanketOrder.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not bo:
        raise HTTPException(status_code=404, detail="ჩარჩო შეთანხმება არ მოიძებნა")
    bo.status = "active"
    await db.flush()
    return ResponseBase(data={"id": str(bo.id)}, message="ჩარჩო შეთანხმება აქტიურია")


# ── Vendor scorecard ──────────────────────────────────────────────────────────

@router.post("/scorecards", response_model=ResponseBase[dict], status_code=201)
async def upsert_scorecard(
    payload: ScorecardIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    company_id = current_user.company_id
    await _require_supplier(db, company_id, payload.supplier_id)
    existing = (await db.execute(
        select(SupplierScorecard).where(
            SupplierScorecard.company_id == company_id,
            SupplierScorecard.supplier_id == payload.supplier_id,
            SupplierScorecard.period == payload.period,
        )
    )).scalar_one_or_none()
    overall = None
    rates = [r for r in (payload.on_time_delivery_rate, payload.quality_rate, payload.price_index) if r is not None]
    if rates:
        overall = Decimal(str(sum(rates) / len(rates)))
    if existing:
        existing.on_time_delivery_rate = payload.on_time_delivery_rate
        existing.quality_rate = payload.quality_rate
        existing.price_index = payload.price_index
        existing.overall_score = overall
        existing.notes = payload.notes
        await db.flush()
        return ResponseBase(data={"id": str(existing.id)}, message="სკორკარდი განახლებულია")
    sc = SupplierScorecard(
        company_id=company_id, supplier_id=payload.supplier_id, period=payload.period,
        on_time_delivery_rate=payload.on_time_delivery_rate, quality_rate=payload.quality_rate,
        price_index=payload.price_index, overall_score=overall, notes=payload.notes,
    )
    db.add(sc)
    await db.flush()
    return ResponseBase(data={"id": str(sc.id)}, message="სკორკარდი შექმნილია")


@router.get("/scorecards", response_model=ResponseBase[list[dict]])
async def list_scorecards(
    supplier_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_access")),
):
    query = select(SupplierScorecard).where(SupplierScorecard.company_id == current_user.company_id)
    if supplier_id:
        query = query.where(SupplierScorecard.supplier_id == supplier_id)
    query = query.order_by(SupplierScorecard.period.desc())
    rows = (await db.execute(query)).scalars().all()
    result = []
    for s in rows:
        supplier = (await db.execute(select(Supplier).where(Supplier.id == s.supplier_id))).scalar_one_or_none()
        result.append({
            "id": str(s.id), "supplier_id": str(s.supplier_id),
            "supplier_name": supplier.name if supplier else "—",
            "period": s.period,
            "on_time_delivery_rate": float(s.on_time_delivery_rate) if s.on_time_delivery_rate else None,
            "quality_rate": float(s.quality_rate) if s.quality_rate else None,
            "price_index": float(s.price_index) if s.price_index else None,
            "overall_score": float(s.overall_score) if s.overall_score else None,
            "orders_count": s.orders_count, "on_time_orders": s.on_time_orders,
        })
    return ResponseBase(data=result)


# ── Auto-replenishment → purchase order ───────────────────────────────────────

@router.post("/auto-replenish", response_model=ResponseBase[dict])
async def auto_replenish(
    warehouse_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_create")),
):
    """Generate a draft purchase order from replenishment suggestions."""
    company_id = current_user.company_id
    rules = (await db.execute(
        select(ReplenishmentRule).where(
            ReplenishmentRule.company_id == company_id,
            ReplenishmentRule.is_active.is_(True),
        )
    )).scalars().all()
    if warehouse_id:
        rules = [r for r in rules if r.warehouse_id == warehouse_id]

    suggestions = []
    for rule in rules:
        balance = (await db.execute(
            select(InventoryBalance).where(
                InventoryBalance.company_id == company_id,
                InventoryBalance.warehouse_id == rule.warehouse_id,
                InventoryBalance.product_id == rule.product_id,
            )
        )).scalar_one_or_none()
        on_hand = Decimal(balance.quantity) if balance else Decimal("0")
        if on_hand < rule.min_quantity:
            reorder = rule.reorder_quantity or (rule.max_quantity - on_hand)
            if reorder > 0:
                suggestions.append({
                    "product_id": str(rule.product_id),
                    "warehouse_id": str(rule.warehouse_id),
                    "quantity": float(max(reorder, Decimal("0"))),
                })
    if not suggestions:
        return ResponseBase(data={"created": False, "message": "შევსება არ არის საჭირო"})

    count = await db.scalar(select(func.count(PurchaseOrder.id)).where(PurchaseOrder.company_id == company_id))
    po = PurchaseOrder(
        company_id=company_id,
        purchase_order_number=f"PO-{datetime.now():%Y%m%d}-{int(count or 0) + 1:04d}",
        status="draft",
        notes="ავტომატური replenishment-ით გენერირებული",
    )
    db.add(po)
    await db.flush()
    for s in suggestions:
        db.add(PurchaseOrderItem(
            purchase_order_id=po.id, product_id=UUID(s["product_id"]),
            quantity=Decimal(str(s["quantity"])),
        ))
    await db.flush()
    return ResponseBase(
        data={"created": True, "purchase_order_id": str(po.id), "order_number": po.purchase_order_number, "items": suggestions},
        message=f"შექმნილია {len(suggestions)} ხაზიანი შესყიდვის შეკვეთა",
    )

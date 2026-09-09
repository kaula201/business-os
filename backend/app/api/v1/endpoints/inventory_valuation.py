"""Inventory valuation API — Odoo-depth: AVCO/FIFO/Standard methods."""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.cost_layer import ProductValuationConfig
from app.models.user import User
from app.services.inventory_valuation import apply_incoming_movement, get_valuation, get_valuation_method
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/inventory/valuation", tags=["საწყობი — შეფასება"])


def require_stock_role(user: User) -> None:
    if user.role not in (User.Role.ADMIN, User.Role.MANAGER, User.Role.ACCOUNTANT):
        raise HTTPException(status_code=403, detail="ოპერაცია ხელმისაწვდომია მხოლოდ ადმინ/მენეჯერ/ბუღალტერისთვის")


class ValuationAdjust(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    note: str | None = None


class ValuationResult(BaseModel):
    product_id: uuid.UUID
    quantity: float
    weighted_avg_cost: float
    total_value: float


class ValuationSummary(BaseModel):
    total_products: int
    total_quantity: float
    total_value: float
    gl_inventory_balance: float
    difference: float
    reconciled: bool
    # P0.2: explicit status — never claim "reconciled" on an empty source
    status: str = "no_data"  # no_data | computing | reconciled | difference | gl_posting_needed
    source_count: int = 0    # products actually included in the valuation


@router.get("/summary", response_model=ValuationSummary)
async def valuation_summary(
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reconcile inventory valuation against the GL inventory account (1200)."""
    require_stock_role(current_user)
    from sqlalchemy import func, select as sa_select
    from app.models.gl import GLAccount, JournalEntryLine, JournalEntry
    from app.models.product import Product
    from app.models.warehouse import InventoryBalance

    # Valuation from on-hand balances × weighted average cost (purchase_price)
    rows = (await db.execute(
        sa_select(Product.id, Product.current_stock, Product.purchase_price)
        .join(InventoryBalance, InventoryBalance.product_id == Product.id)
        .where(
            Product.company_id == current_user.company_id,
            InventoryBalance.company_id == current_user.company_id,
        )
    )).all()

    total_value = Decimal("0")
    total_qty = Decimal("0")
    product_ids = set()
    for product_id, qty, unit_cost in rows:
        if not qty or qty <= 0:
            continue
        product_ids.add(str(product_id))
        total_qty += Decimal(str(qty))
        total_value += Decimal(str(qty)) * Decimal(str(unit_cost or 0))

    # GL 1200 (inventory) balance: debit - credit
    gl_row = (await db.execute(
        sa_select(
            func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("dr"),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("cr"),
        )
        .select_from(JournalEntryLine)
        .join(GLAccount, GLAccount.id == JournalEntryLine.gl_account_id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(GLAccount.company_id == current_user.company_id, GLAccount.code == "1200")
    )).one()
    gl_balance = Decimal(gl_row.dr) - Decimal(gl_row.cr)

    diff = (total_value - gl_balance).quantize(Decimal("0.01"))

    # P0.2: business-meaningful status — never "reconciled" on an empty source
    if len(product_ids) == 0:
        status = "no_data"
        reconciled = False
    elif abs(diff) < Decimal("0.01"):
        status = "reconciled"
        reconciled = True
    elif gl_balance == Decimal("0") and total_value > 0:
        status = "gl_posting_needed"
        reconciled = False
    else:
        status = "difference"
        reconciled = False

    return ValuationSummary(
        total_products=len(product_ids),
        total_quantity=float(total_qty.quantize(Decimal("0.01"))),
        total_value=float(total_value.quantize(Decimal("0.01"))),
        gl_inventory_balance=float(gl_balance.quantize(Decimal("0.01"))),
        difference=float(diff),
        reconciled=reconciled,
        status=status,
        source_count=len(product_ids),
    )
@router.get("/{product_id:uuid}", response_model=ValuationResult)
async def get_product_valuation(
    product_id: uuid.UUID,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_stock_role(current_user)
    try:
        return await get_valuation(db, current_user.company_id, product_id)
    except ValueError as e:
        if str(e) == "product_not_found":
            raise HTTPException(status_code=404, detail="პროდუქტი ვერ მოიძებნა")
        raise


@router.post("/adjust", response_model=ValuationResult)
async def adjust_valuation(
    data: ValuationAdjust,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually inject an incoming layer (e.g. opening balance / correction)."""
    require_stock_role(current_user)
    try:
        layer = await apply_incoming_movement(
            db,
            current_user.company_id,
            data.product_id,
            data.quantity,
            data.unit_cost,
        )
        await db.commit()
        result = await get_valuation(db, current_user.company_id, data.product_id)
        return ValuationResult(**result)
    except ValueError as e:
        if str(e) == "product_not_found":
            raise HTTPException(status_code=404, detail="პროდუქტი ვერ მოიძებნა")
        raise


# ═══════════════════════ Valuation method config (Odoo) ═══════════════════════

@router.get("/methods", response_model=dict)
async def list_valuation_methods(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-product valuation method: standard | avco | fifo."""
    rows = (await db.execute(
        select(ProductValuationConfig).where(
            ProductValuationConfig.company_id == current_user.company_id,
        )
    )).scalars().all()
    return {
        "data": [{
            "product_id": str(c.product_id),
            "method": c.method,
            "standard_cost": float(c.standard_cost),
        } for c in rows],
        "message": None,
    }


@router.post("/methods", response_model=dict)
async def set_valuation_method(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a product's valuation method (standard/avco/fifo) + standard cost."""
    require_stock_role(current_user)
    method = data.get("method", "avco")
    if method not in ("standard", "avco", "fifo"):
        raise HTTPException(status_code=422, detail="მეთოდი უნდა იყოს standard, avco ან fifo")

    cfg = (await db.execute(select(ProductValuationConfig).where(
        ProductValuationConfig.company_id == current_user.company_id,
        ProductValuationConfig.product_id == data["product_id"],
    ))).scalar_one_or_none()
    if cfg:
        cfg.method = method
        if data.get("standard_cost") is not None:
            cfg.standard_cost = Decimal(str(data["standard_cost"]))
    else:
        cfg = ProductValuationConfig(
            company_id=current_user.company_id,
            product_id=data["product_id"],
            method=method,
            standard_cost=Decimal(str(data.get("standard_cost", 0))),
        )
        db.add(cfg)
    await db.commit()
    return {"data": {"product_id": str(cfg.product_id), "method": cfg.method}, "message": "მეთოდი დაყენდა"}


# ═══════════════════ Inventory Valuation 2.0 ═══════════════════

@router.post("/methods/negative-stock", response_model=dict)
async def set_negative_stock_policy(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Negative stock policy: allow/forbid negative quantities per product."""
    require_stock_role(current_user)
    cfg = (await db.execute(select(ProductValuationConfig).where(
        ProductValuationConfig.company_id == current_user.company_id,
        ProductValuationConfig.product_id == data["product_id"],
    ))).scalar_one_or_none()
    if cfg is None:
        cfg = ProductValuationConfig(
            company_id=current_user.company_id,
            product_id=data["product_id"],
            method="avco",
            standard_cost=Decimal("0"),
        )
        db.add(cfg)
    cfg.negative_stock_allowed = bool(data.get("negative_stock_allowed", False))
    await db.commit()
    return {"data": {"product_id": str(cfg.product_id), "negative_stock_allowed": cfg.negative_stock_allowed}, "message": "პოლიტიკა დაყენდა"}


@router.post("/apply-landed-cost", response_model=dict)
async def apply_landed_cost_to_valuation(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Landed cost → valuation layer: bump cost layers by allocated amounts."""
    from app.models.wms_ops import LandedCost, LandedCostAllocation
    from app.models.warehouse import ProductBatch
    from app.models.cost_layer import FifoCostLot

    landed_cost_id = data.get("landed_cost_id")
    if landed_cost_id:
        lc = (await db.execute(select(LandedCost).where(
            LandedCost.id == landed_cost_id,
            LandedCost.company_id == current_user.company_id,
        ))).scalar_one_or_none()
        if not lc:
            raise HTTPException(status_code=404, detail="Landed cost არ მოიძებნა")
        allocations = (await db.execute(select(LandedCostAllocation).where(
            LandedCostAllocation.landed_cost_id == lc.id,
        ))).scalars().all()
        if not allocations:
            raise HTTPException(status_code=400, detail="Landed cost არ არის გადანაწილებული")
        total = Decimal("0")
        for alloc in allocations:
            batch = (await db.execute(select(ProductBatch).where(ProductBatch.id == alloc.batch_id))).scalar_one_or_none()
            unit_bump = (alloc.amount / batch.quantity) if batch and batch.quantity and batch.quantity > 0 else Decimal("0")
            if not batch:
                continue
            # bump matching FIFO cost lots for the batch product
            lots = (await db.execute(
                select(FifoCostLot).where(
                    FifoCostLot.company_id == current_user.company_id,
                    FifoCostLot.product_id == alloc.product_id,
                    FifoCostLot.quantity_remaining > 0,
                ).order_by(FifoCostLot.received_at)
            )).scalars().all()
            remaining_alloc = alloc.amount
            for lot in lots:
                if remaining_alloc <= 0:
                    break
                lot.unit_cost += unit_bump
                remaining_alloc -= unit_bump * lot.quantity_remaining
            total += alloc.amount
        lc.allocated = True
        await db.commit()
        return {"data": {"landed_cost_id": str(lc.id), "allocated_total": float(total)}, "message": "Landed cost valuation-ში ასახულია"}
    raise HTTPException(status_code=400, detail="landed_cost_id აუცილებელია")


@router.post("/apply-production-cost", response_model=dict)
async def apply_production_cost_to_valuation(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Production cost → valuation: inject production output at its cost."""
    from app.services.inventory_valuation import apply_incoming_movement
    product_id = data.get("product_id")
    quantity = data.get("quantity")
    unit_cost = data.get("unit_cost")
    if not product_id or not quantity or unit_cost is None:
        raise HTTPException(status_code=400, detail="product_id, quantity, unit_cost აუცილებელია")
    layer = await apply_incoming_movement(
        db, current_user.company_id, product_id, Decimal(str(quantity)), Decimal(str(unit_cost)),
    )
    await db.commit()
    return {"data": {"product_id": str(product_id), "quantity": float(layer.quantity_remaining), "unit_cost": float(layer.weighted_avg_cost)}, "message": "Production cost valuation-ში ასახულია"}


@router.post("/adjust-to-gl", response_model=dict)
async def post_adjustment_to_gl(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stock adjustment → GL: create journal entry for adjustment value."""
    from app.services.gl_posting import get_account_map, post_journal_entry
    from app.models.product import Product

    product_id = data.get("product_id")
    quantity_delta = data.get("quantity_delta")
    unit_cost = data.get("unit_cost")
    note = data.get("note", "მარაგის კორექტირება")
    if not product_id or quantity_delta is None or unit_cost is None:
        raise HTTPException(status_code=400, detail="product_id, quantity_delta, unit_cost აუცილებელია")
    product = (await db.execute(select(Product).where(
        Product.id == product_id, Product.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")
    value = Decimal(str(quantity_delta)) * Decimal(str(unit_cost))
    from datetime import date as _date
    entry_date = _date.fromisoformat(data["entry_date"]) if data.get("entry_date") else _date.today()
    await post_journal_entry(
        db, current_user.company_id, current_user,
        entry_date=entry_date,
        description=f"{note} — {product.name} ({quantity_delta} × {unit_cost})",
        reference_type="stock_adjustment",
        reference_id=uuid.uuid4(),
        lines=[
            ("1200", abs(value) if value > 0 else Decimal("0"), Decimal("0")),
            ("5100", Decimal("0"), abs(value) if value > 0 else Decimal("0")),
        ] if value >= 0 else [
            ("5100", abs(value), Decimal("0")),
            ("1200", Decimal("0"), abs(value)),
        ],
    )
    await db.commit()
    return {"data": {"adjustment_value": float(abs(value)), "entry_type": "stock_adjustment"}, "message": "კორექტირება GL-ში აისახა"}


@router.get("/reconciliations", response_model=dict)
async def list_reconciliations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Period-end inventory reconciliations."""
    from app.models.cost_layer import InventoryReconciliation as IR
    rows = (await db.execute(select(IR).where(
        IR.company_id == current_user.company_id,
    ).order_by(IR.created_at.desc()))).scalars().all()
    return {"data": [{
        "id": str(r.id), "reconciliation_number": r.reconciliation_number,
        "warehouse_id": str(r.warehouse_id), "status": r.status,
        "period_start": r.period_start.isoformat(), "period_end": r.period_end.isoformat(),
        "total_book_value": float(r.total_book_value), "total_counted_value": float(r.total_counted_value),
        "total_adjustment": float(r.total_adjustment),
    } for r in rows], "message": None}


@router.post("/reconciliations", response_model=dict)
async def create_reconciliation(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create period-end reconciliation: compare book vs counted value."""
    from datetime import datetime
    from app.models.cost_layer import InventoryReconciliation as IR, ReconciliationLine as RL
    from app.models.warehouse import InventoryBalance
    from app.services.inventory_valuation import get_valuation

    warehouse_id = data.get("warehouse_id")
    lines_data = data.get("lines", [])
    period_end = datetime.fromisoformat(data.get("period_end", _today_iso()))
    if not warehouse_id or not lines_data:
        raise HTTPException(status_code=400, detail="warehouse_id და lines აუცილებელია")

    seq_num = f"REC-{uuid.uuid4().hex[:6].upper()}"
    total_book = Decimal("0")
    total_counted = Decimal("0")
    lines = []
    for ld in lines_data:
        product_id = ld["product_id"]
        counted = Decimal(str(ld.get("counted_quantity", 0)))
        balance = (await db.execute(select(InventoryBalance).where(
            InventoryBalance.company_id == current_user.company_id,
            InventoryBalance.warehouse_id == warehouse_id,
            InventoryBalance.product_id == product_id,
        ))).scalar_one_or_none()
        book_qty = balance.quantity if balance else Decimal("0")
        val = await get_valuation(db, current_user.company_id, product_id)
        unit_cost = Decimal(str(val["weighted_avg_cost"]))
        diff = counted - book_qty
        adj_value = diff * unit_cost
        total_book += book_qty * unit_cost
        total_counted += counted * unit_cost
        lines.append(RL(
            product_id=product_id, book_quantity=book_qty, counted_quantity=counted,
            difference_quantity=diff, unit_cost=unit_cost, adjustment_value=adj_value,
            notes=ld.get("notes"),
        ))
    rec = IR(
        company_id=current_user.company_id, warehouse_id=warehouse_id,
        reconciliation_number=seq_num, period_start=period_end.replace(day=1),
        period_end=period_end, status="draft",
        total_book_value=total_book, total_counted_value=total_counted,
        total_adjustment=total_counted - total_book, created_by=current_user.id,
    )
    db.add(rec)
    await db.flush()
    for l in lines:
        l.reconciliation_id = rec.id
        db.add(l)
    await db.commit()
    return {"data": {"id": str(rec.id), "reconciliation_number": seq_num, "total_adjustment": float(rec.total_adjustment)}, "message": "რეკონსილაცია შექმნილია"}


@router.post("/reconciliations/{reconciliation_id}/post", response_model=dict)
async def post_reconciliation(
    reconciliation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Post reconciliation → GL: adjustment journal entry for the difference."""
    from app.models.cost_layer import InventoryReconciliation as IR
    rec = (await db.execute(select(IR).where(
        IR.id == reconciliation_id, IR.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="რეკონსილაცია არ მოიძებნა")
    if rec.total_adjustment != Decimal("0"):
        from app.services.gl_posting import post_journal_entry
        adj = rec.total_adjustment
        lines = [
            ("1200", adj, Decimal("0")),
            ("5100", Decimal("0"), adj),
        ] if adj > 0 else [
            ("5100", abs(adj), Decimal("0")),
            ("1200", Decimal("0"), abs(adj)),
        ]
        await post_journal_entry(
            db, current_user.company_id, current_user,
            entry_date=rec.period_end.date(),
            description=f"პერიოდის დახურვა — ინვენტარის რეკონსილაცია {rec.reconciliation_number}",
            reference_type="inventory_reconciliation",
            reference_id=rec.id,
            lines=lines,
        )
    rec.status = "posted"
    await db.commit()
    return {"data": {"id": str(rec.id), "status": "posted", "adjustment": float(rec.total_adjustment)}, "message": "რეკონსილაცია დაპოსტილია"}


@router.get("/locations", response_model=dict)
async def list_location_valuations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-location inventory value."""
    from app.models.cost_layer import LocationValuation as LV
    rows = (await db.execute(select(LV).where(
        LV.company_id == current_user.company_id,
    ))).scalars().all()
    return {"data": [{
        "id": str(r.id), "warehouse_id": str(r.warehouse_id),
        "zone_id": str(r.zone_id) if r.zone_id else None,
        "product_id": str(r.product_id), "quantity": float(r.quantity),
        "unit_cost": float(r.unit_cost), "total_value": float(r.total_value),
    } for r in rows], "message": None}


@router.post("/locations", response_model=dict)
async def upsert_location_valuation(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create/update per-location valuation row."""
    from app.models.cost_layer import LocationValuation as LV
    existing = (await db.execute(select(LV).where(
        LV.company_id == current_user.company_id,
        LV.warehouse_id == data["warehouse_id"],
        LV.zone_id == (data.get("zone_id") or None),
        LV.product_id == data["product_id"],
    ))).scalar_one_or_none()
    if existing is None:
        existing = LV(
            company_id=current_user.company_id, warehouse_id=data["warehouse_id"],
            zone_id=data.get("zone_id"), product_id=data["product_id"],
        )
        db.add(existing)
    existing.quantity = Decimal(str(data.get("quantity", 0)))
    existing.unit_cost = Decimal(str(data.get("unit_cost", 0)))
    existing.total_value = existing.quantity * existing.unit_cost
    await db.commit()
    return {"data": {"id": str(existing.id), "total_value": float(existing.total_value)}, "message": "მდებარეობის შეფასება შენახულია"}


def _today_iso() -> str:
    from datetime import date
    return date.today().isoformat()

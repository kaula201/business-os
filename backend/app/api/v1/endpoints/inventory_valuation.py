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
@router.get("/{product_id}", response_model=ValuationResult)
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

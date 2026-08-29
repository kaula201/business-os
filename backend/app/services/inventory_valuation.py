"""Inventory valuation service — Odoo-depth: AVCO layers, FIFO lots, Standard cost.

Semantics:
  - Incoming movement (in): quantity increases, weighted average cost
    recomputed as (old_qty*old_avg + qty*cost) / (old_qty + qty).
    For FIFO a cost lot is created; for Standard the product's standard_cost
    is used as the unit cost.
  - Outgoing movement (out): quantity decreases; COGS value =
    qty * current weighted_avg_cost (AVCO), or FIFO lots consumed oldest-first,
    or qty * standard_cost (Standard).
"""
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost_layer import FifoCostLot, ProductCostLayer, ProductValuationConfig
from app.models.product import Product


def money(value, places: int = 4) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01").scaleb(0) if places == 2 else Decimal("1").scaleb(-places), rounding=ROUND_HALF_UP)


def money2(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def get_valuation_method(db: AsyncSession, company_id: uuid.UUID, product_id: uuid.UUID) -> str:
    """Return the product's valuation method: standard | avco | fifo (default avco)."""
    cfg = (await db.execute(select(ProductValuationConfig).where(
        ProductValuationConfig.company_id == company_id,
        ProductValuationConfig.product_id == product_id,
    ))).scalar_one_or_none()
    return cfg.method if cfg else "avco"


async def ensure_layer(db: AsyncSession, company_id: uuid.UUID, product_id: uuid.UUID) -> ProductCostLayer:
    """Get or create the cost layer for a product (defaults to purchase_price)."""
    layer = (
        await db.execute(
            select(ProductCostLayer).where(
                ProductCostLayer.company_id == company_id,
                ProductCostLayer.product_id == product_id,
            ).with_for_update()
        )
    ).scalar_one_or_none()
    if layer is not None:
        return layer

    product = (
        await db.execute(select(Product).where(
            Product.id == product_id, Product.company_id == company_id,
        ))
    ).scalar_one_or_none()
    if product is None:
        raise ValueError("product_not_found")
    default_cost = Decimal(str(product.purchase_price)) if product.purchase_price else Decimal("0")

    layer = ProductCostLayer(
        company_id=company_id,
        product_id=product_id,
        quantity_remaining=Decimal("0"),
        weighted_avg_cost=money(default_cost),
    )
    db.add(layer)
    await db.flush()
    return layer


async def apply_incoming_movement(
    db: AsyncSession,
    company_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: Decimal,
    unit_cost: Decimal,
    movement_id: uuid.UUID | None = None,
    receipt_id: uuid.UUID | None = None,
) -> ProductCostLayer:
    """Add an incoming movement (goods receipt / purchase).

    AVCO: recompute weighted average. FIFO: create a cost lot. Standard:
    use the configured standard_cost as the layer cost.
    """
    method = await get_valuation_method(db, company_id, product_id)
    layer = await ensure_layer(db, company_id, product_id)
    old_qty = Decimal(layer.quantity_remaining)
    old_cost = Decimal(layer.weighted_avg_cost)
    qty = Decimal(quantity)
    cost = Decimal(unit_cost)

    if method == "standard":
        cfg = (await db.execute(select(ProductValuationConfig).where(
            ProductValuationConfig.company_id == company_id,
            ProductValuationConfig.product_id == product_id,
        ))).scalar_one_or_none()
        cost = cfg.standard_cost if cfg and cfg.standard_cost else cost

    new_qty = old_qty + qty
    if new_qty > 0:
        layer.weighted_avg_cost = money(
            (old_qty * old_cost + qty * cost) / new_qty
        )
    layer.quantity_remaining = money(new_qty, 3)
    layer.last_movement_id = movement_id

    if method == "fifo":
        db.add(FifoCostLot(
            company_id=company_id,
            product_id=product_id,
            purchase_receipt_id=receipt_id,
            quantity_remaining=qty,
            unit_cost=cost,
        ))
    await db.flush()
    return layer


async def apply_outgoing_movement(
    db: AsyncSession,
    company_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: Decimal,
    movement_id: uuid.UUID | None = None,
) -> tuple[ProductCostLayer, Decimal]:
    """Apply an outgoing movement; returns (layer, cogs_value).

    AVCO: COGS = qty * current weighted_avg_cost.
    FIFO: consume cost lots oldest-first.
    Standard: COGS = qty * standard_cost.
    """
    method = await get_valuation_method(db, company_id, product_id)
    layer = await ensure_layer(db, company_id, product_id)
    qty = Decimal(quantity)

    if method == "fifo":
        cogs = Decimal("0")
        remaining = qty
        lots = (await db.execute(
            select(FifoCostLot).where(
                FifoCostLot.company_id == company_id,
                FifoCostLot.product_id == product_id,
                FifoCostLot.quantity_remaining > 0,
            ).order_by(FifoCostLot.created_at.asc()).with_for_update()
        )).scalars().all()
        for lot in lots:
            if remaining <= 0:
                break
            take = min(lot.quantity_remaining, remaining)
            cogs += take * lot.unit_cost
            lot.quantity_remaining = money(lot.quantity_remaining - take, 3)
            remaining -= take
        if remaining > 0:
            # fall back to the layer average for uncovered qty
            cogs += remaining * Decimal(layer.weighted_avg_cost)
    elif method == "standard":
        cfg = (await db.execute(select(ProductValuationConfig).where(
            ProductValuationConfig.company_id == company_id,
            ProductValuationConfig.product_id == product_id,
        ))).scalar_one_or_none()
        std = cfg.standard_cost if cfg and cfg.standard_cost else Decimal(layer.weighted_avg_cost)
        cogs = money2(qty * std)
    else:
        avg = Decimal(layer.weighted_avg_cost)
        cogs = money2(qty * avg)

    remaining_qty = Decimal(layer.quantity_remaining) - qty
    layer.quantity_remaining = money(remaining_qty, 3)
    layer.last_movement_id = movement_id
    await db.flush()
    return layer, cogs


async def get_valuation(
    db: AsyncSession,
    company_id: uuid.UUID,
    product_id: uuid.UUID,
) -> dict:
    """Return current valuation of a product's remaining stock."""
    method = await get_valuation_method(db, company_id, product_id)
    layer = await ensure_layer(db, company_id, product_id)
    qty = Decimal(layer.quantity_remaining)
    avg = Decimal(layer.weighted_avg_cost)
    return {
        "product_id": str(product_id),
        "method": method,
        "quantity": float(qty),
        "weighted_avg_cost": float(avg),
        "total_value": float(money2(qty * avg)),
    }

"""Inventory valuation service — weighted-average cost (WAC) layers.

Semantics:
  - Incoming movement (in): quantity increases, weighted average cost
    recomputed as (old_qty*old_avg + qty*cost) / (old_qty + qty).
  - Outgoing movement (out): quantity decreases; COGS value =
    qty * current weighted_avg_cost. Layer quantity decreases; the
    average cost itself stays unchanged until the next incoming layer.
"""
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost_layer import ProductCostLayer
from app.models.product import Product


def money(value, places: int = 4) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01").scaleb(0) if places == 2 else Decimal("1").scaleb(-places), rounding=ROUND_HALF_UP)


def money2(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
) -> ProductCostLayer:
    """Add an incoming movement (goods receipt / purchase)."""
    layer = await ensure_layer(db, company_id, product_id)
    old_qty = Decimal(layer.quantity_remaining)
    old_cost = Decimal(layer.weighted_avg_cost)
    qty = Decimal(quantity)
    cost = Decimal(unit_cost)

    new_qty = old_qty + qty
    if new_qty > 0:
        layer.weighted_avg_cost = money(
            (old_qty * old_cost + qty * cost) / new_qty
        )
    layer.quantity_remaining = money(new_qty, 3)
    layer.last_movement_id = movement_id
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

    COGS value = quantity * current weighted_avg_cost.
    """
    layer = await ensure_layer(db, company_id, product_id)
    qty = Decimal(quantity)
    avg = Decimal(layer.weighted_avg_cost)
    cogs = money2(qty * avg)

    remaining = Decimal(layer.quantity_remaining) - qty
    layer.quantity_remaining = money(remaining, 3)
    layer.last_movement_id = movement_id
    await db.flush()
    return layer, cogs


async def get_valuation(
    db: AsyncSession,
    company_id: uuid.UUID,
    product_id: uuid.UUID,
) -> dict:
    """Return current valuation of a product's remaining stock."""
    layer = await ensure_layer(db, company_id, product_id)
    qty = Decimal(layer.quantity_remaining)
    avg = Decimal(layer.weighted_avg_cost)
    return {
        "product_id": str(product_id),
        "quantity": float(qty),
        "weighted_avg_cost": float(avg),
        "total_value": float(money2(qty * avg)),
    }

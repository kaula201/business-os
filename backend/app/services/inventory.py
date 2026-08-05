from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.warehouse import InventoryBalance


async def sync_product_current_stock(
    db: AsyncSession,
    *,
    company_id: UUID,
    product_id: UUID,
) -> float:
    """Synchronize the denormalized product stock from warehouse balances."""
    product = (
        await db.execute(
            select(Product)
            .where(
                Product.id == product_id,
                Product.company_id == company_id,
            )
            .with_for_update()
        )
    ).scalar_one()
    total = (
        await db.execute(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                InventoryBalance.company_id == company_id,
                InventoryBalance.product_id == product_id,
            )
        )
    ).scalar_one()
    stock = float(Decimal(total))
    product.current_stock = stock
    return stock

"""Shared revenue metric — single source of truth for Dashboard, AI, Reports, GL."""
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.order import Order


async def get_total_revenue(
    db: AsyncSession,
    company_id: UUID,
) -> Decimal:
    """Canonical revenue: sum of issued (confirmed) invoice totals."""
    result = await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(
            Invoice.company_id == company_id,
            Invoice.status == "issued",
        )
    )
    return Decimal(str(result.scalar()))


async def get_revenue_for_period(
    db: AsyncSession,
    company_id: UUID,
    date_from,
    date_to,
) -> Decimal:
    """Revenue from issued invoices within a date range."""
    result = await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(
            Invoice.company_id == company_id,
            Invoice.status == "issued",
            Invoice.invoice_date >= date_from,
            Invoice.invoice_date <= date_to,
        )
    )
    return Decimal(str(result.scalar()))


async def get_order_based_revenue(
    db: AsyncSession,
    company_id: UUID,
) -> dict:
    """Order-based revenue breakdown (for Dashboard KPI context)."""
    result = await db.execute(
        select(
            func.coalesce(func.sum(Order.total), 0),
            func.count(Order.id),
        )
        .where(
            Order.company_id == company_id,
            Order.status.in_(["completed", "confirmed", "preparing", "shipping"]),
        )
    )
    row = result.one()
    return {
        "total": float(row[0] or 0),
        "count": row[1] or 0,
    }

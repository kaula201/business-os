from datetime import date, datetime, time
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.purchase import PurchaseCostHistory
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.purchase_cost import PurchaseCostHistoryResponse

router = APIRouter(prefix="/purchase-cost-history", tags=["შესყიდვის თვითღირებულება"])


def build_response(row: PurchaseCostHistory) -> PurchaseCostHistoryResponse:
    return PurchaseCostHistoryResponse(
        id=row.id,
        product_id=row.product_id,
        product_name=row.product.name,
        supplier_id=row.supplier_id,
        supplier_name=row.supplier.name,
        purchase_order_id=row.purchase_order_id,
        purchase_order_number=row.purchase_order.purchase_order_number,
        goods_receipt_id=row.goods_receipt_id,
        receipt_number=row.goods_receipt.receipt_number,
        quantity=float(row.quantity),
        unit_cost=float(row.unit_cost),
        previous_stock=float(row.previous_stock),
        new_stock=float(row.new_stock),
        previous_average_cost=float(row.previous_average_cost),
        new_average_cost=float(row.new_average_cost),
        created_at=row.created_at,
    )


@router.get("/", response_model=ResponseBase[PaginatedResponse[PurchaseCostHistoryResponse]])
async def list_purchase_cost_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    product_id: UUID | None = None,
    supplier_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [PurchaseCostHistory.company_id == current_user.company_id]
    if product_id:
        filters.append(PurchaseCostHistory.product_id == product_id)
    if supplier_id:
        filters.append(PurchaseCostHistory.supplier_id == supplier_id)
    if date_from:
        filters.append(PurchaseCostHistory.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        filters.append(PurchaseCostHistory.created_at <= datetime.combine(date_to, time.max))

    total = (await db.execute(
        select(func.count(PurchaseCostHistory.id)).where(*filters)
    )).scalar_one()
    rows = (
        await db.execute(
            select(PurchaseCostHistory)
            .where(*filters)
            .options(
                selectinload(PurchaseCostHistory.product),
                selectinload(PurchaseCostHistory.supplier),
                selectinload(PurchaseCostHistory.purchase_order),
                selectinload(PurchaseCostHistory.goods_receipt),
            )
            .order_by(PurchaseCostHistory.created_at.desc(), PurchaseCostHistory.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).unique().scalars().all()
    return ResponseBase(data=PaginatedResponse(
        items=[build_response(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))

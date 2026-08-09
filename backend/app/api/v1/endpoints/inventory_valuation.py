"""Inventory valuation API — weighted-average cost layers."""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.inventory_valuation import apply_incoming_movement, get_valuation

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

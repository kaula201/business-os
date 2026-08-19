"""Financial automation API — manual trigger of the monthly period-close."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import ResponseBase
from app.services.financial_automation import run_financial_automation_for_company

router = APIRouter(prefix="/gl/automation", tags=["ფინანსური ავტომატიზაცია"])


@router.post("/run", response_model=ResponseBase[dict])
async def run_automation(
    company_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the monthly close for the current company (or a specified one) now."""
    if current_user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="ავტომატიზაციის გაშვების უფლება არ გაქვთ")

    target_company = company_id or current_user.company_id
    if company_id and company_id != current_user.company_id and current_user.role != User.Role.ADMIN:
        raise HTTPException(status_code=403, detail="სხვა კომპანიის გაშვება მხოლოდ ადმინის შეუძლია")

    result = await run_financial_automation_for_company(db, target_company)
    if result.get("skipped"):
        raise HTTPException(status_code=422, detail=result.get("reason", "გაშვება შეუძლებელია"))
    return ResponseBase(
        data=result,
        message="ფინანსური ავტომატიზაცია დასრულდა — depreciation, FX, deferred",
    )

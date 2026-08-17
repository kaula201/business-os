"""Field-level access endpoints — per-role field visibility rules."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.field_access import FieldAccessRule
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/field-access", tags=["ველების წვდომა"])


@router.get("/", response_model=ResponseBase[list[dict]])
async def list_rules(
    module: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("security", "can_access")),
):
    query = select(FieldAccessRule).where(FieldAccessRule.company_id == current_user.company_id)
    if module:
        query = query.where(FieldAccessRule.module == module)
    result = await db.execute(query.order_by(FieldAccessRule.module, FieldAccessRule.role, FieldAccessRule.field))
    return ResponseBase(data=[{
        "id": str(r.id), "module": r.module, "role": r.role, "field": r.field,
        "can_view": r.can_view, "can_edit": r.can_edit,
    } for r in result.scalars().all()])


@router.post("/", response_model=ResponseBase[dict], status_code=201)
async def create_rule(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("security", "can_create")),
):
    rule = FieldAccessRule(
        company_id=current_user.company_id,
        module=data.get("module", ""),
        role=data.get("role", "employee"),
        field=data.get("field", ""),
        can_view=bool(data.get("can_view", True)),
        can_edit=bool(data.get("can_edit", False)),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return ResponseBase(data={"id": str(rule.id), "module": rule.module, "role": rule.role, "field": rule.field}, message="წესი შეიქმნა")


@router.delete("/{rule_id}", response_model=ResponseBase[dict])
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("security", "can_delete")),
):
    result = await db.execute(
        select(FieldAccessRule).where(FieldAccessRule.id == rule_id, FieldAccessRule.company_id == current_user.company_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="წესი არ მოიძებნა")
    await db.delete(rule)
    await db.commit()
    return ResponseBase(data={"id": str(rule_id)}, message="წესი წაიშალა")

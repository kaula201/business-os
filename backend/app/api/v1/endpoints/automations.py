"""Automation endpoints — trigger → action rules CRUD."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.automation import AutomationRule
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/automations", tags=["ავტომატიზაცია"])


@router.get("/", response_model=ResponseBase[list[dict]])
async def list_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("automations", "can_access")),
):
    result = await db.execute(
        select(AutomationRule)
        .where(AutomationRule.company_id == current_user.company_id)
        .order_by(AutomationRule.created_at.desc())
    )
    return ResponseBase(data=[{
        "id": str(r.id), "name": r.name, "trigger": r.trigger,
        "action": r.action, "target": r.target, "is_active": r.is_active,
    } for r in result.scalars().all()])


@router.post("/", response_model=ResponseBase[dict], status_code=201)
async def create_rule(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("automations", "can_create")),
):
    rule = AutomationRule(
        company_id=current_user.company_id,
        name=data.get("name", ""),
        trigger=data.get("trigger", ""),
        action=data.get("action", "notify"),
        target=data.get("target"),
        is_active=bool(data.get("is_active", True)),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return ResponseBase(data={"id": str(rule.id), "name": rule.name}, message="წესი შეიქმნა")


@router.patch("/{rule_id}", response_model=ResponseBase[dict])
async def update_rule(
    rule_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("automations", "can_edit")),
):
    result = await db.execute(
        select(AutomationRule).where(
            AutomationRule.id == rule_id,
            AutomationRule.company_id == current_user.company_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="წესი არ მოიძებნა")
    if "is_active" in data:
        rule.is_active = bool(data["is_active"])
    if "name" in data:
        rule.name = data["name"]
    await db.commit()
    return ResponseBase(data={"id": str(rule_id)}, message="წესი განახლდა")


@router.delete("/{rule_id}", response_model=ResponseBase[dict])
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("automations", "can_delete")),
):
    result = await db.execute(
        select(AutomationRule).where(
            AutomationRule.id == rule_id,
            AutomationRule.company_id == current_user.company_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="წესი არ მოიძებნა")
    await db.delete(rule)
    await db.commit()
    return ResponseBase(data={"id": str(rule_id)}, message="წესი წაიშალა")

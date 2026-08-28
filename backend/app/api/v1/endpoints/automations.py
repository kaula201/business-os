"""Automation endpoints — trigger → action rules CRUD."""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.automation import AutomationRule
from app.models.email_calendar import EmailMessage
from app.models.task import Task
from app.models.user import User
from app.schemas.common import ResponseBase
from app.services.email_service import send_email_smtp, smtp_configured

router = APIRouter(prefix="/automations", tags=["ავტომატიზაცია"])

# Triggers the rule engine reacts to.
KNOWN_TRIGGERS = {"invoice_issued", "order_created", "stock_low", "task_overdue", "client_created"}


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


@router.post("/trigger/{trigger}", response_model=ResponseBase[dict])
async def run_trigger(
    trigger: str,
    data: dict | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fire a business event; every active rule matching the trigger runs its action."""
    if trigger not in KNOWN_TRIGGERS:
        raise HTTPException(status_code=422, detail=f"უცნობი trigger: {trigger}")

    rules = (await db.execute(
        select(AutomationRule).where(
            AutomationRule.company_id == current_user.company_id,
            AutomationRule.trigger == trigger,
            AutomationRule.is_active.is_(True),
        )
    )).scalars().all()

    data = data or {}
    executed = []
    for rule in rules:
        try:
            if rule.action == "send_email":
                target = data.get("email") or rule.target
                if not target:
                    continue
                subject = data.get("subject") or f"შეტყობინება: {trigger}"
                body = data.get("body") or (
                    f"მოვლენა: {trigger}\n"
                    f"ობიექტი: {data.get('entity', '—')} {data.get('entity_id', '')}\n"
                    f"დეტალები: {data.get('details', '—')}"
                )
                if smtp_configured():
                    send_email_smtp(target, subject, body)
                else:
                    db.add(EmailMessage(
                        company_id=current_user.company_id, to_email=target,
                        subject=subject, body=body, status="sent",
                    ))
                    await db.flush()
            elif rule.action == "create_task":
                assignee_id = data.get("assignee_id") or current_user.id
                db.add(Task(
                    company_id=current_user.company_id,
                    title=data.get("task_title") or f"[ავტომატური] {rule.name}",
                    description=data.get("details", ""),
                    status="todo",
                    priority=data.get("priority", "medium"),
                    assigned_to=assignee_id,
                    due_date=data.get("due_date") or (datetime.utcnow() + timedelta(days=2)),
                    created_by=current_user.id,
                ))
                await db.flush()
            else:  # notify
                db.add(EmailMessage(
                    company_id=current_user.company_id,
                    to_email=rule.target or current_user.email,
                    subject=f"შეტყობინება: {trigger}",
                    body=data.get("details", f"მოვლენა: {trigger}"),
                    status="sent",
                ))
                await db.flush()
            executed.append({"rule": rule.name, "action": rule.action})
        except Exception:
            continue

    await db.commit()
    return ResponseBase(
        data={"trigger": trigger, "matched_rules": len(rules), "executed": executed},
        message=f"Trigger {trigger} დამუშავდა — {len(executed)} წესი შესრულდა",
    )

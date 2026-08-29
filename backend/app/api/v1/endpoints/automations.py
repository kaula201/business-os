"""Automation endpoints — trigger → condition → action rules CRUD + engine."""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.automation import AutomationRule, KNOWN_TRIGGERS, KNOWN_ACTIONS
from app.models.email_calendar import EmailMessage
from app.models.notification import Notification
from app.models.task import Task
from app.models.user import User
from app.schemas.common import ResponseBase
from app.services.email_service import send_email_smtp, smtp_configured

router = APIRouter(prefix="/automations", tags=["ავტომატიზაცია"])


def _matches_conditions(conditions: list | None, payload: dict) -> bool:
    """Evaluate JSON conditions against the event payload (AND logic).

    op: eq | neq | gt | gte | lt | lte | contains | in | is_set
    field may be nested via dots: "items.total" → payload["items"]["total"].
    """
    if not conditions:
        return True
    for cond in conditions:
        field = cond.get("field", "")
        op = cond.get("op", "eq")
        expected = cond.get("value")
        # resolve nested field
        value: object = payload
        for part in field.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break
        try:
            if op == "eq":
                ok = value == expected
            elif op == "neq":
                ok = value != expected
            elif op == "gt":
                ok = value is not None and float(value) > float(expected)
            elif op == "gte":
                ok = value is not None and float(value) >= float(expected)
            elif op == "lt":
                ok = value is not None and float(value) < float(expected)
            elif op == "lte":
                ok = value is not None and float(value) <= float(expected)
            elif op == "contains":
                ok = expected in str(value or "")
            elif op == "in":
                ok = value in (expected or [])
            elif op == "is_set":
                ok = value is not None and value != ""
            else:
                ok = True  # unknown op → pass
        except (TypeError, ValueError):
            ok = False
        if not ok:
            return False
    return True


@router.get("/meta", response_model=ResponseBase[dict])
async def automation_meta(current_user: User = Depends(get_current_user)):
    """Return the trigger/action/op vocabulary for the rule builder UI."""
    return ResponseBase(data={
        "triggers": sorted(KNOWN_TRIGGERS),
        "actions": sorted(KNOWN_ACTIONS),
        "operators": ["eq", "neq", "gt", "gte", "lt", "lte", "contains", "in", "is_set"],
    })


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
        "conditions": r.conditions, "action": r.action, "target": r.target,
        "payload": r.payload, "is_active": r.is_active,
        "run_count": r.run_count, "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
    } for r in result.scalars().all()])


@router.post("/", response_model=ResponseBase[dict], status_code=201)
async def create_rule(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("automations", "can_create")),
):
    trigger = data.get("trigger", "")
    action = data.get("action", "notify")
    if trigger and trigger not in KNOWN_TRIGGERS:
        raise HTTPException(status_code=422, detail=f"უცნობი trigger: {trigger}")
    if action not in KNOWN_ACTIONS:
        raise HTTPException(status_code=422, detail=f"უცნობი action: {action}")
    rule = AutomationRule(
        company_id=current_user.company_id,
        name=data.get("name", ""),
        trigger=trigger,
        conditions=data.get("conditions"),
        action=action,
        target=data.get("target"),
        payload=data.get("payload"),
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
    for key in ("is_active", "name", "trigger", "action", "target", "conditions", "payload"):
        if key in data:
            setattr(rule, key, data[key])
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
    """Fire a business event; every active rule matching the trigger AND its
    conditions runs its action. Tracks run_count / last_run_at."""
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
    skipped_conditions = 0
    now = datetime.utcnow()
    for rule in rules:
        if not _matches_conditions(rule.conditions, data):
            skipped_conditions += 1
            continue
        try:
            payload = rule.payload or {}
            if rule.action == "send_email":
                target = data.get("email") or rule.target
                if not target:
                    continue
                subject = data.get("subject") or payload.get("subject") or f"შეტყობინება: {trigger}"
                body = data.get("body") or payload.get("body") or (
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
                assignee_id = data.get("assignee_id") or payload.get("assignee_id") or current_user.id
                db.add(Task(
                    company_id=current_user.company_id,
                    title=data.get("task_title") or payload.get("task_title") or f"[ავტომატური] {rule.name}",
                    description=data.get("details", ""),
                    status="todo",
                    priority=data.get("priority", "medium"),
                    assigned_to=assignee_id,
                    due_date=data.get("due_date") or payload.get("due_date") or (now + timedelta(days=2)),
                    created_by=current_user.id,
                ))
                await db.flush()
            elif rule.action == "notify":
                target_user_id = None
                try:
                    target_user_id = uuid.UUID(rule.target) if rule.target else None
                except (ValueError, TypeError):
                    target_user_id = None
                if target_user_id and target_user_id != current_user.id:
                    db.add(Notification(
                        company_id=current_user.company_id,
                        user_id=target_user_id,
                        type="automation",
                        title=f"ავტომატიზაცია: {rule.name}",
                        message=data.get("details", f"მოვლენა: {trigger}"),
                        link=data.get("entity_id", ""),
                    ))
                else:
                    db.add(EmailMessage(
                        company_id=current_user.company_id,
                        to_email=rule.target or current_user.email,
                        subject=f"შეტყობინება: {trigger}",
                        body=data.get("details", f"მოვლენა: {trigger}"),
                        status="sent",
                    ))
                await db.flush()
            elif rule.action == "update_status":
                # entity status auto-advance: payload.status_to applied if allowed
                status_to = payload.get("status_to")
                if status_to:
                    entity = data.get("entity")
                    entity_id = data.get("entity_id")
                    if entity == "order":
                        from app.models.order import Order
                        from app.api.v1.endpoints.orders import ALLOWED_TRANSITIONS
                        order = (await db.execute(select(Order).where(
                            Order.id == uuid.UUID(str(entity_id)),
                            Order.company_id == current_user.company_id,
                        ))).scalar_one_or_none()
                        if order:
                            current_status = order.status.value if hasattr(order.status, "value") else order.status
                            allowed = ALLOWED_TRANSITIONS.get(current_status, set())
                            if status_to in allowed:
                                order.status = status_to
                                await db.flush()
            elif rule.action == "webhook":
                import httpx
                url = rule.target or payload.get("url")
                if url and url.startswith("http"):
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        await client.post(url, json={"trigger": trigger, **data})
            executed.append({"rule": rule.name, "action": rule.action})
            rule.run_count = (rule.run_count or 0) + 1
            rule.last_run_at = now
        except Exception:
            continue

    await db.commit()
    return ResponseBase(
        data={
            "trigger": trigger, "matched_rules": len(rules),
            "executed": executed, "skipped_conditions": skipped_conditions,
        },
        message=f"Trigger {trigger} დამუშავდა — {len(executed)} წესი შესრულდა, {skipped_conditions} გამოტოვებული (conditions)",
    )

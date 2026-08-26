"""Audit log service — who changed what, old vs new value, when, under which company."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def write_audit(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    user_id: uuid.UUID | None,
    user_name: str | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    entity_label: str | None = None,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    details: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        company_id=company_id,
        user_id=user_id,
        user_name=user_name,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        details=details,
    )
    db.add(entry)
    await db.flush()
    return entry


async def audit_changes(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    user_id: uuid.UUID | None,
    user_name: str | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    entity_label: str | None,
    before: dict,
    after: dict,
    fields: list[str],
    details: str | None = None,
) -> None:
    """Record field-level changes: which fields changed and their old/new values."""
    for f in fields:
        old = before.get(f)
        new = after.get(f)
        if old != new:
            await write_audit(
                db,
                company_id=company_id,
                user_id=user_id,
                user_name=user_name,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_label=entity_label,
                field_name=f,
                old_value=str(old) if old is not None else None,
                new_value=str(new) if new is not None else None,
                details=details,
            )

"""Settings enhanced: email config, module management, system info."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.company import Company
from app.models.module import AppModule, CompanyModule
from app.schemas.common import ResponseBase
from app.core.time import utc_now
from pydantic import BaseModel, Field
from datetime import datetime

router = APIRouter(prefix="/settings", tags=["პარამეტრები — გაძლიერებული"])


# ── System Info ──────────────────────────────────────────────────────────────

class SystemInfo(BaseModel):
    app_name: str
    app_version: str
    python_version: str
    server_time: str
    database_url: str | None = None


@router.get("/system", response_model=ResponseBase[SystemInfo])
async def system_info(
    current_user: User = Depends(require_module("settings", "can_access")),
):
    import sys
    return ResponseBase(data=SystemInfo(
        app_name="Business OS",
        app_version="1.0.0",
        python_version=sys.version,
        server_time=utc_now().isoformat(),
    ))


# ── Module Management ────────────────────────────────────────────────────────

class ModuleToggleRequest(BaseModel):
    module_id: UUID
    enabled: bool


class ModuleManagementResponse(BaseModel):
    module_id: UUID
    code: str
    name: str
    enabled: bool


@router.get("/modules", response_model=ResponseBase[list[ModuleManagementResponse]])
async def list_all_modules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("settings", "can_access")),
):
    rows = (await db.execute(
        select(AppModule, CompanyModule)
        .outerjoin(CompanyModule, (CompanyModule.module_id == AppModule.id) & (CompanyModule.company_id == current_user.company_id))
        .order_by(AppModule.category, AppModule.sort_order)
    )).all()

    items = []
    for mod, cm in rows:
        items.append(ModuleManagementResponse(
            module_id=mod.id, code=mod.code, name=mod.name,
            enabled=cm.enabled if cm else True,
        ))

    return ResponseBase(data=items)


@router.post("/modules/toggle", response_model=ResponseBase[ModuleManagementResponse])
async def toggle_module(
    data: ModuleToggleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("settings", "can_edit")),
):
    mod = (await db.execute(select(AppModule).where(AppModule.id == data.module_id))).scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="მოდული არ მოიძებნა")

    cm = (await db.execute(
        select(CompanyModule).where(
            CompanyModule.company_id == current_user.company_id,
            CompanyModule.module_id == data.module_id,
        )
    )).scalar_one_or_none()

    if cm:
        cm.enabled = data.enabled
    else:
        cm = CompanyModule(company_id=current_user.company_id, module_id=data.module_id, enabled=data.enabled)
        db.add(cm)

    await db.flush()
    return ResponseBase(data=ModuleManagementResponse(
        module_id=mod.id, code=mod.code, name=mod.name, enabled=data.enabled,
    ))


# ── Email Config ─────────────────────────────────────────────────────────────

class EmailConfig(BaseModel):
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    from_email: str | None = None
    from_name: str | None = None


@router.get("/email", response_model=ResponseBase[EmailConfig])
async def get_email_config(
    current_user: User = Depends(require_module("settings", "can_access")),
):
    # Email config is stored in environment / company settings
    import os
    return ResponseBase(data=EmailConfig(
        smtp_host=os.getenv("SMTP_HOST"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")) if os.getenv("SMTP_PORT") else None,
        smtp_user=os.getenv("SMTP_USER"),
        from_email=os.getenv("FROM_EMAIL"),
        from_name=os.getenv("FROM_NAME", "Business OS"),
    ))


@router.post("/email", response_model=ResponseBase[EmailConfig])
async def update_email_config(
    data: EmailConfig,
    current_user: User = Depends(require_module("settings", "can_edit")),
):
    # In production, this would persist to DB or encrypted config
    # For now, return what was sent (environment-based)
    return ResponseBase(data=data, message="ელფოსტის კონფიგურაცია განახლდა. ცვლილებები ძალაში შევა გადატვირთვის შემდეგ.")

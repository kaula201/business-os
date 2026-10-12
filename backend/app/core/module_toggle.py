"""Shared module-toggle guard and write path (#41)."""
from uuid import UUID
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.module import AppModule, CompanyModule


async def require_module_toggler(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """
    Guard for module toggle endpoints (issue #41).

    - Rejects any request carrying X-API-Key, even with admin scopes.
    - Authenticates interactive JWT only.
    - Requires admin role.
    - Enforces `settings:can_edit` permission via existing dependency.
    """
    if "X-API-Key" in request.headers:
        raise HTTPException(
            status_code=403,
            detail="API გასაღებით მოდულის ჩართვა/გამორთვა აკრძალულია"
        )

    user = await get_current_user(request, db)

    if user.role != User.Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="მხოლოდ ადმინისტრატორს შეუძლია"
        )

    # enforce settings:can_edit
    await require_module("settings", "can_edit")(request, db, user)

    return user


async def set_company_module_enabled(
    db: AsyncSession,
    company_id: UUID,
    module_id: UUID,
    enabled: bool
) -> tuple[AppModule, CompanyModule]:
    """
    Central helper to enable/disable a module for a company (issue #41).

    Loads an active AppModule, then updates or creates the corresponding
    CompanyModule row. Returns the AppModule and the CompanyModule after flush/refresh.
    """
    result = await db.execute(select(AppModule).where(AppModule.id == module_id))
    mod = result.scalar_one_or_none()
    if mod is None:
        raise HTTPException(status_code=404, detail="მოდული არ მოიძებნა")
    if not mod.is_active:
        raise HTTPException(status_code=403, detail="მოდული არააქტიურია")

    result = await db.execute(
        select(CompanyModule).where(
            CompanyModule.company_id == company_id,
            CompanyModule.module_id == module_id
        )
    )
    cm = result.scalar_one_or_none()

    if cm is None:
        cm = CompanyModule(company_id=company_id, module_id=module_id, enabled=enabled)
        db.add(cm)
    else:
        cm.enabled = enabled

    await db.flush()
    await db.refresh(cm)

    return mod, cm

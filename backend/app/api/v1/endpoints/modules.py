"""App Module Registry API — Odoo-inspired module management.

Endpoints:
  GET    /modules/              — list all available modules (admin)
  POST   /modules/              — register a new module (admin)
  GET    /modules/{id}          — get module details
  PATCH  /modules/{id}          — update module (admin)
  DELETE /modules/{id}          — soft-deactivate module (admin)
  GET    /modules/company       — get company's module status (all modules + enabled state)
  POST   /modules/company/{module_id}/toggle — enable/disable a module for the company
  GET    /modules/permissions/{module_id}    — get permissions for a module
  POST   /modules/permissions/{module_id}    — upsert a permission row
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import User
from app.models.module import AppModule, CompanyModule, ModulePermission
from app.schemas.module import (
    AppModuleCreate,
    AppModuleUpdate,
    AppModuleResponse,
    AppModuleWithPermissions,
    CompanyModuleCreate,
    CompanyModuleUpdate,
    CompanyModuleResponse,
    CompanyModuleStatus,
    ModulePermissionCreate,
    ModulePermissionUpdate,
    ModulePermissionResponse,
)
from app.schemas.common import ResponseBase, PaginatedResponse

router = APIRouter(prefix="/modules", tags=["მოდულები"])


# ── AppModule CRUD ──────────────────────────────────────────────────────────────


@router.get("/", response_model=ResponseBase[PaginatedResponse[AppModuleResponse]])
async def list_modules(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    query = select(AppModule)
    if category:
        query = query.where(AppModule.category == category)
    if is_active is not None:
        query = query.where(AppModule.is_active == is_active)
    query = query.order_by(AppModule.sort_order, AppModule.code)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    modules = result.scalars().all()

    return ResponseBase(data=PaginatedResponse(
        items=[AppModuleResponse.model_validate(m) for m in modules],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/", response_model=ResponseBase[AppModuleResponse], status_code=201)
async def create_module(
    data: AppModuleCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    existing = await db.execute(select(AppModule).where(AppModule.code == data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"მოდული '{data.code}' უკვე რეგისტრირებულია")

    module = AppModule(**data.model_dump())
    db.add(module)
    await db.flush()
    await db.refresh(module)
    return ResponseBase(data=AppModuleResponse.model_validate(module))


@router.get("/company", response_model=ResponseBase[list[CompanyModuleStatus]])
async def get_company_modules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return every active module with its enabled state for the current company."""
    mod_result = await db.execute(
        select(AppModule).where(AppModule.is_active == True).order_by(AppModule.sort_order, AppModule.code)
    )
    all_modules = mod_result.scalars().all()

    cm_result = await db.execute(
        select(CompanyModule).where(CompanyModule.company_id == current_user.company_id)
    )
    company_modules = {cm.module_id: cm for cm in cm_result.scalars().all()}

    result: list[CompanyModuleStatus] = []
    for mod in all_modules:
        cm = company_modules.get(mod.id)
        enabled = cm.enabled if cm else True  # default enabled

        perm_result = await db.execute(
            select(ModulePermission).where(ModulePermission.module_id == mod.id)
        )
        perms = perm_result.scalars().all()

        result.append(CompanyModuleStatus(
            module=AppModuleResponse.model_validate(mod),
            enabled=enabled,
            permissions=[ModulePermissionResponse.model_validate(p) for p in perms],
        ))

    return ResponseBase(data=result)


@router.post("/company/{module_id}/toggle", response_model=ResponseBase[CompanyModuleResponse])
async def toggle_company_module(
    module_id: UUID,
    data: CompanyModuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enable or disable a module for the current company."""
    # Verify module exists and is active
    mod_result = await db.execute(
        select(AppModule).where(AppModule.id == module_id, AppModule.is_active == True)
    )
    if not mod_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="მოდული არ მოიძებნა ან არააქტიურია")

    # Find or create CompanyModule row
    cm_result = await db.execute(
        select(CompanyModule).where(
            CompanyModule.company_id == current_user.company_id,
            CompanyModule.module_id == module_id,
        )
    )
    cm = cm_result.scalar_one_or_none()

    if cm:
        cm.enabled = data.enabled
    else:
        cm = CompanyModule(
            company_id=current_user.company_id,
            module_id=module_id,
            enabled=data.enabled,
        )
        db.add(cm)

    await db.flush()
    await db.refresh(cm)
    return ResponseBase(data=CompanyModuleResponse.model_validate(cm))


@router.get("/{module_id}", response_model=ResponseBase[AppModuleWithPermissions])
async def get_module(
    module_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(AppModule).where(AppModule.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="მოდული არ მოიძებნა")

    perm_result = await db.execute(
        select(ModulePermission).where(ModulePermission.module_id == module_id)
    )
    permissions = perm_result.scalars().all()

    resp = AppModuleWithPermissions.model_validate(module)
    resp.permissions = [ModulePermissionResponse.model_validate(p) for p in permissions]
    return ResponseBase(data=resp)


# ── Module Permissions ──────────────────────────────────────────────────────────


@router.get("/permissions/{module_id}", response_model=ResponseBase[list[ModulePermissionResponse]])
async def list_module_permissions(
    module_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(ModulePermission).where(ModulePermission.module_id == module_id)
    )
    perms = result.scalars().all()
    return ResponseBase(data=[ModulePermissionResponse.model_validate(p) for p in perms])


@router.post("/permissions/{module_id}", response_model=ResponseBase[ModulePermissionResponse])
async def upsert_module_permission(
    module_id: UUID,
    data: ModulePermissionCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Create or update a permission row for a (module, role) pair."""
    # Verify module exists
    mod_result = await db.execute(select(AppModule).where(AppModule.id == module_id))
    if not mod_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="მოდული არ მოიძებნა")

    # Check existing
    existing = await db.execute(
        select(ModulePermission).where(
            ModulePermission.module_id == module_id,
            ModulePermission.role == data.role,
        )
    )
    perm = existing.scalar_one_or_none()

    if perm:
        for field, value in data.model_dump(exclude={"module_id", "role"}).items():
            setattr(perm, field, value)
    else:
        perm = ModulePermission(**data.model_dump())
        db.add(perm)

    await db.flush()
    await db.refresh(perm)
    return ResponseBase(data=ModulePermissionResponse.model_validate(perm))

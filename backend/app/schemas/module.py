"""Pydantic schemas for App Module architecture."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── AppModule ──────────────────────────────────────────────────────────────────

class AppModuleBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=100)
    route: Optional[str] = Field(None, max_length=255)
    category: str = Field("other", max_length=50)
    depends_on: Optional[str] = Field(None, max_length=255)
    sort_order: int = 0


class AppModuleCreate(AppModuleBase):
    pass


class AppModuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=100)
    route: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    depends_on: Optional[str] = Field(None, max_length=255)
    sort_order: Optional[int] = None


class AppModuleResponse(AppModuleBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── CompanyModule ───────────────────────────────────────────────────────────────

class CompanyModuleBase(BaseModel):
    module_id: UUID
    enabled: bool = True


class CompanyModuleCreate(CompanyModuleBase):
    pass


class CompanyModuleUpdate(BaseModel):
    enabled: bool


class CompanyModuleResponse(CompanyModuleBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    module: Optional[AppModuleResponse] = None

    model_config = {"from_attributes": True}


# ── ModulePermission ────────────────────────────────────────────────────────────

class ModulePermissionBase(BaseModel):
    module_id: UUID
    role: str = Field(..., max_length=20)
    can_access: bool = True
    can_create: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_approve: bool = False


class ModulePermissionCreate(ModulePermissionBase):
    pass


class ModulePermissionUpdate(BaseModel):
    can_access: Optional[bool] = None
    can_create: Optional[bool] = None
    can_edit: Optional[bool] = None
    can_delete: Optional[bool] = None
    can_approve: Optional[bool] = None


class ModulePermissionResponse(ModulePermissionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    module: Optional[AppModuleResponse] = None

    model_config = {"from_attributes": True}


# ── Module with permissions (nested) ────────────────────────────────────────────

class AppModuleWithPermissions(AppModuleResponse):
    permissions: list[ModulePermissionResponse] = []


# ── Company module status (for frontend) ───────────────────────────────────────

class CompanyModuleStatus(BaseModel):
    """Returned by GET /api/v1/modules/company — shows every module with its enabled state."""
    module: AppModuleResponse
    enabled: bool
    permissions: list[ModulePermissionResponse] = []

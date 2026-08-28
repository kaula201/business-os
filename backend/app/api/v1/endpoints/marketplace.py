"""Marketplace API — app catalog, install/uninstall, per-company config."""
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.marketplace import CompanyAppInstallation, MarketplaceApp
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


def _app_dict(a: MarketplaceApp, installed: bool = False, config: dict | None = None) -> dict:
    return {
        "id": str(a.id), "name": a.name, "slug": a.slug,
        "description": a.description, "category": a.category, "icon": a.icon,
        "version": a.version, "publisher": a.publisher, "price": a.price,
        "is_published": a.is_published, "permissions": a.permissions,
        "config_schema": a.config_schema, "installed": installed, "config": config,
    }


# ── Catalog (global) ──────────────────────────────────────────────────────────

@router.get("/apps", response_model=ResponseBase[PaginatedResponse[dict]])
async def list_marketplace_apps(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [MarketplaceApp.is_published.is_(True)]
    if category:
        filters.append(MarketplaceApp.category == category)
    total = (await db.execute(select(func.count(MarketplaceApp.id)).where(*filters))).scalar_one()
    rows = (await db.execute(
        select(MarketplaceApp).where(*filters)
        .order_by(MarketplaceApp.name).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    installed_ids = set((await db.execute(select(CompanyAppInstallation.app_id).where(
        CompanyAppInstallation.company_id == current_user.company_id,
        CompanyAppInstallation.status == "installed",
    ))).scalars().all())

    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[_app_dict(a, installed=a.id in installed_ids) for a in rows],
    ))


@router.get("/apps/{app_id:uuid}", response_model=ResponseBase[dict])
async def get_marketplace_app(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    app = (await db.execute(select(MarketplaceApp).where(
        MarketplaceApp.id == app_id, MarketplaceApp.is_published.is_(True),
    ))).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="აპი არ მოიძებნა")
    inst = (await db.execute(select(CompanyAppInstallation).where(
        CompanyAppInstallation.app_id == app_id,
        CompanyAppInstallation.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    return ResponseBase(data=_app_dict(
        app, installed=inst is not None and inst.status == "installed",
        config=inst.config if inst else None,
    ))


# ── Admin: publish apps ───────────────────────────────────────────────────────

@router.post("/apps", response_model=ResponseBase[dict], status_code=201)
async def create_marketplace_app(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_create")),
):
    if current_user.role != User.Role.ADMIN:
        raise HTTPException(status_code=403, detail="მხოლოდ ადმინს შეუძლია აპის გამოქვეყნება")
    app = MarketplaceApp(
        name=data["name"], slug=data.get("slug") or data["name"].lower().replace(" ", "-"),
        description=data.get("description"), category=data.get("category", "other"),
        icon=data.get("icon", "Package"), version=data.get("version", "1.0.0"),
        publisher=data.get("publisher", "Business OS"), price=float(data.get("price", 0)),
        is_published=bool(data.get("is_published", True)),
        permissions=data.get("permissions"), config_schema=data.get("config_schema"),
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return ResponseBase(data={"id": str(app.id), "name": app.name}, message="აპი გამოქვეყნდა")


# ── Install / uninstall ───────────────────────────────────────────────────────

@router.post("/apps/{app_id:uuid}/install", response_model=ResponseBase[dict])
async def install_marketplace_app(
    app_id: UUID,
    data: dict | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_edit")),
):
    app = (await db.execute(select(MarketplaceApp).where(
        MarketplaceApp.id == app_id, MarketplaceApp.is_published.is_(True),
    ))).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="აპი არ მოიძებნა")

    inst = (await db.execute(select(CompanyAppInstallation).where(
        CompanyAppInstallation.app_id == app_id,
        CompanyAppInstallation.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if inst:
        inst.status = "installed"
        if data and data.get("config"):
            inst.config = data["config"]
    else:
        inst = CompanyAppInstallation(
            company_id=current_user.company_id, app_id=app_id,
            status="installed", config=(data or {}).get("config"),
            installed_by=current_user.id,
        )
        db.add(inst)
    await db.commit()
    return ResponseBase(data={"id": str(app_id), "status": "installed"}, message="აპი დაყენდა")


@router.post("/apps/{app_id:uuid}/uninstall", response_model=ResponseBase[dict])
async def uninstall_marketplace_app(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_edit")),
):
    inst = (await db.execute(select(CompanyAppInstallation).where(
        CompanyAppInstallation.app_id == app_id,
        CompanyAppInstallation.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="აპი არ არის დაყენებული")
    inst.status = "uninstalled"
    await db.commit()
    return ResponseBase(data={"id": str(app_id), "status": "uninstalled"}, message="აპი მოიხსნა")


@router.patch("/apps/{app_id:uuid}/config", response_model=ResponseBase[dict])
async def update_app_config(
    app_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_edit")),
):
    inst = (await db.execute(select(CompanyAppInstallation).where(
        CompanyAppInstallation.app_id == app_id,
        CompanyAppInstallation.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="აპი არ არის დაყენებული")
    inst.config = data.get("config", inst.config)
    await db.commit()
    return ResponseBase(data={"id": str(app_id)}, message="კონფიგურაცია შეინახა")


# ── My installed apps ─────────────────────────────────────────────────────────

@router.get("/my-apps", response_model=ResponseBase[list[dict]])
async def my_installed_apps(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(CompanyAppInstallation).where(
            CompanyAppInstallation.company_id == current_user.company_id,
            CompanyAppInstallation.status == "installed",
        ).options(selectinload(CompanyAppInstallation.app))
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(i.app_id), "name": i.app.name, "slug": i.app.slug,
        "icon": i.app.icon, "category": i.app.category, "version": i.app.version,
        "config": i.config, "installed_at": i.installed_at.isoformat(),
    } for i in rows])

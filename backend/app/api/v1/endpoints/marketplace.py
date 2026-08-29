"""Marketplace API — app catalog, install/uninstall, per-company config."""
import uuid
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.marketplace import CompanyAppInstallation, MarketplaceApp, MarketplacePurchase
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


# ═══════════════════════ Billing — purchase, trial, license ═══════════════════

@router.post("/apps/{app_id:uuid}/purchase", response_model=ResponseBase[dict])
async def purchase_app(
    app_id: UUID,
    data: dict | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_edit")),
):
    """Buy a paid app. Stripe charge when configured, else sandbox 'paid'."""
    from app.core.config import settings
    from app.models.marketplace import MarketplacePurchase
    from app.api.v1.endpoints.purchase_orders import allocate_document_number
    from decimal import Decimal

    app = (await db.execute(select(MarketplaceApp).where(
        MarketplaceApp.id == app_id, MarketplaceApp.is_published.is_(True),
    ))).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="აპი არ მოიძებნა")
    if app.price <= 0:
        raise HTTPException(status_code=400, detail="აპი უფასოა — purchase არ არის საჭირო")

    billing_mode = (data or {}).get("billing_mode", "one_time")
    amount = app.price
    payment_reference = None
    status = "paid"

    if settings.STRIPE_SECRET_KEY:
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            pi = stripe.PaymentIntent.create(
                amount=int(amount * 100), currency="gel",
                payment_method_types=["card"],
                metadata={"app": app.slug, "company_id": str(current_user.company_id)},
            )
            payment_reference = pi.id
        except Exception:
            status = "failed"

    invoice_number = await allocate_document_number(db, current_user.company_id, "marketplace_invoice", "INV-MP")
    purchase = MarketplacePurchase(
        company_id=current_user.company_id, app_id=app_id,
        amount=Decimal(str(amount)), billing_mode=billing_mode,
        status=status, payment_reference=payment_reference,
        invoice_number=invoice_number, purchased_by=current_user.id,
    )
    db.add(purchase)

    # activate the installation with license
    inst = (await db.execute(select(CompanyAppInstallation).where(
        CompanyAppInstallation.app_id == app_id,
        CompanyAppInstallation.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if inst:
        inst.status = "installed"
        inst.billing_mode = billing_mode
        inst.license_key = f"LIC-{uuid.uuid4().hex[:12].upper()}"
    else:
        inst = CompanyAppInstallation(
            company_id=current_user.company_id, app_id=app_id,
            status="installed", billing_mode=billing_mode,
            license_key=f"LIC-{uuid.uuid4().hex[:12].upper()}",
            installed_by=current_user.id,
        )
        db.add(inst)
    await db.commit()
    return ResponseBase(data={
        "purchase_id": str(purchase.id), "invoice_number": invoice_number,
        "amount": float(amount), "status": status,
        "payment_reference": payment_reference, "license_key": inst.license_key,
        "gateway": "stripe" if settings.STRIPE_SECRET_KEY else "sandbox",
    }, message="აპი შეძენილია")


@router.post("/apps/{app_id:uuid}/trial", response_model=ResponseBase[dict])
async def start_app_trial(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("integrations", "can_edit")),
):
    """Start a 14-day trial for a paid app."""
    from datetime import timedelta

    app = (await db.execute(select(MarketplaceApp).where(
        MarketplaceApp.id == app_id, MarketplaceApp.is_published.is_(True),
    ))).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="აპი არ მოიძებნა")

    inst = (await db.execute(select(CompanyAppInstallation).where(
        CompanyAppInstallation.app_id == app_id,
        CompanyAppInstallation.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if inst and inst.billing_mode == "trial" and inst.trial_ends_at and inst.trial_ends_at > datetime.utcnow():
        raise HTTPException(status_code=400, detail="ტრიალი უკვე აქტიურია")

    trial_end = datetime.utcnow() + timedelta(days=14)
    if inst:
        inst.status = "trial"
        inst.billing_mode = "trial"
        inst.trial_ends_at = trial_end
    else:
        inst = CompanyAppInstallation(
            company_id=current_user.company_id, app_id=app_id,
            status="trial", billing_mode="trial", trial_ends_at=trial_end,
            installed_by=current_user.id,
        )
        db.add(inst)
    await db.commit()
    return ResponseBase(data={
        "id": str(inst.id), "status": "trial",
        "trial_ends_at": trial_end.isoformat(),
    }, message="14-დღიანი ტრიალი დაიწყო")


@router.get("/purchases", response_model=ResponseBase[list[dict]])
async def list_purchases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MarketplacePurchase).where(
            MarketplacePurchase.company_id == current_user.company_id,
        ).order_by(MarketplacePurchase.created_at.desc()).limit(100)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(p.id), "app_id": str(p.app_id),
        "amount": float(p.amount), "billing_mode": p.billing_mode,
        "status": p.status, "invoice_number": p.invoice_number,
        "payment_reference": p.payment_reference,
        "created_at": p.created_at.isoformat(),
    } for p in rows])

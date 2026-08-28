"""PLM API — product versions, engineering changes (ECO), lifecycle stages."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.plm import EngineeringChange, ProductLifecycle, ProductVersion
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/plm", tags=["PLM"])


# ── Product versions ────────────────────────────────────────────────


@router.get("/products/{product_id}/versions", response_model=ResponseBase[list[dict]])
async def list_versions(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(ProductVersion).where(
            ProductVersion.product_id == product_id,
            ProductVersion.company_id == current_user.company_id,
        ).order_by(ProductVersion.revision.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(v.id), "version": v.version, "revision": v.revision,
        "bom_id": str(v.bom_id) if v.bom_id else None, "is_current": v.is_current,
        "notes": v.notes, "created_at": v.created_at.isoformat(),
    } for v in rows])


@router.post("/products/{product_id}/versions", response_model=ResponseBase[dict], status_code=201)
async def create_version(
    product_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # demote current versions
    cur = (await db.execute(
        select(ProductVersion).where(
            ProductVersion.product_id == product_id,
            ProductVersion.company_id == current_user.company_id,
            ProductVersion.is_current.is_(True),
        )
    )).scalars().all()
    for c in cur:
        c.is_current = False
    max_rev = max((v.revision for v in cur), default=0)
    v = ProductVersion(
        company_id=current_user.company_id,
        product_id=product_id,
        version=data.get("version", f"v{max_rev + 1}.0"),
        revision=max_rev + 1,
        bom_id=data.get("bom_id"),
        specs=data.get("specs"),
        notes=data.get("notes"),
        is_current=True,
        created_by=current_user.id,
    )
    db.add(v)
    await db.flush()
    return ResponseBase(data={"id": str(v.id), "version": v.version, "revision": v.revision}, message="ვერსია შეიქმნა")


# ── Engineering changes (ECO) ───────────────────────────────────────


@router.get("/engineering-changes", response_model=ResponseBase[list[dict]])
async def list_ecos(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(EngineeringChange).where(EngineeringChange.company_id == current_user.company_id)
    if status:
        q = q.where(EngineeringChange.status == status)
    rows = (await db.execute(q.order_by(EngineeringChange.created_at.desc()))).scalars().all()
    return ResponseBase(data=[{
        "id": str(e.id), "eco_number": e.eco_number, "product_id": str(e.product_id),
        "title": e.title, "change_type": e.change_type, "priority": e.priority,
        "status": e.status, "impact_cost": float(e.impact_cost),
    } for e in rows])


@router.post("/engineering-changes", response_model=ResponseBase[dict], status_code=201)
async def create_eco(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.api.v1.endpoints.purchase_orders import allocate_document_number
    number = await allocate_document_number(db, current_user.company_id, "engineering_change", "ECO")
    e = EngineeringChange(
        company_id=current_user.company_id,
        eco_number=number,
        product_id=data.get("product_id"),
        title=data.get("title", ""),
        description=data.get("description"),
        change_type=data.get("change_type", "design"),
        priority=data.get("priority", "medium"),
        status=data.get("status", "draft"),
        requested_by=current_user.id,
        impact_cost=data.get("impact_cost", 0),
    )
    db.add(e)
    await db.flush()
    return ResponseBase(data={"id": str(e.id), "eco_number": e.eco_number}, message="ECO შეიქმნა")


@router.patch("/engineering-changes/{eco_id}", response_model=ResponseBase[dict])
async def update_eco(
    eco_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    e = (await db.execute(
        select(EngineeringChange).where(EngineeringChange.id == eco_id, EngineeringChange.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="ECO არ მოიძებნა")
    for field in ("status", "priority", "description", "impact_cost"):
        if field in data:
            setattr(e, field, data[field])
    if data.get("status") == "approved":
        e.approved_by = current_user.id
        e.approved_at = datetime.utcnow()
    await db.flush()
    return ResponseBase(data={"id": str(e.id), "status": e.status}, message="ECO განახლდა")


# ── Product lifecycle ───────────────────────────────────────────────


@router.get("/products/{product_id}/lifecycle", response_model=ResponseBase[dict])
async def get_lifecycle(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lc = (await db.execute(
        select(ProductLifecycle).where(
            ProductLifecycle.product_id == product_id,
            ProductLifecycle.company_id == current_user.company_id,
        )
    )).scalar_one_or_none()
    if not lc:
        return ResponseBase(data={"product_id": str(product_id), "stage": "concept"})
    return ResponseBase(data={
        "product_id": str(lc.product_id), "stage": lc.stage,
        "stage_changed_at": lc.stage_changed_at.isoformat() if lc.stage_changed_at else None,
        "eol_date": lc.eol_date.isoformat() if lc.eol_date else None,
        "notes": lc.notes,
    })


@router.put("/products/{product_id}/lifecycle", response_model=ResponseBase[dict])
async def update_lifecycle(
    product_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lc = (await db.execute(
        select(ProductLifecycle).where(
            ProductLifecycle.product_id == product_id,
            ProductLifecycle.company_id == current_user.company_id,
        )
    )).scalar_one_or_none()
    if not lc:
        lc = ProductLifecycle(company_id=current_user.company_id, product_id=product_id)
        db.add(lc)
    stage = data.get("stage", "concept")
    if stage not in ("concept", "design", "prototype", "production", "eol"):
        raise HTTPException(status_code=422, detail="არასწორი სტადია")
    lc.stage = stage
    lc.stage_changed_at = datetime.utcnow()
    lc.eol_date = data.get("eol_date")
    lc.notes = data.get("notes")
    await db.flush()
    return ResponseBase(data={"product_id": str(product_id), "stage": lc.stage}, message="სასიცოცხლო ციკლი განახლდა")

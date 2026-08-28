"""No-code Studio API — apps, forms, fields, records."""
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.studio import StudioApp, StudioField, StudioForm, StudioRecord
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase

router = APIRouter(prefix="/studio", tags=["No-code Studio"])


def _app_dict(a: StudioApp) -> dict:
    return {
        "id": str(a.id), "name": a.name, "slug": a.slug,
        "description": a.description, "icon": a.icon, "is_active": a.is_active,
        "form_count": len(a.forms) if a.forms else 0,
    }


def _form_dict(f: StudioForm) -> dict:
    return {
        "id": str(f.id), "app_id": str(f.app_id), "name": f.name, "slug": f.slug,
        "layout": f.layout,
        "fields": [{
            "id": str(x.id), "label": x.label, "field_key": x.field_key,
            "field_type": x.field_type, "required": x.required,
            "options": x.options, "placeholder": x.placeholder, "sort_order": x.sort_order,
        } for x in (f.fields or [])],
    }


# ── Apps ──────────────────────────────────────────────────────────────────────

@router.get("/apps", response_model=ResponseBase[list[dict]])
async def list_studio_apps(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("studio", "can_access")),
):
    rows = (await db.execute(
        select(StudioApp).where(StudioApp.company_id == current_user.company_id)
        .options(selectinload(StudioApp.forms)).order_by(StudioApp.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[_app_dict(a) for a in rows])


@router.post("/apps", response_model=ResponseBase[dict], status_code=201)
async def create_studio_app(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("studio", "can_create")),
):
    app = StudioApp(
        company_id=current_user.company_id,
        name=data["name"], slug=data.get("slug") or data["name"].lower().replace(" ", "-"),
        description=data.get("description"), icon=data.get("icon", "AppWindow"),
        created_by=current_user.id,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return ResponseBase(data={"id": str(app.id), "name": app.name}, message="აპი შეიქმნა")


@router.patch("/apps/{app_id}", response_model=ResponseBase[dict])
async def update_studio_app(
    app_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("studio", "can_edit")),
):
    app = (await db.execute(select(StudioApp).where(
        StudioApp.id == app_id, StudioApp.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="აპი არ მოიძებნა")
    for field in ("name", "slug", "description", "icon", "is_active"):
        if field in data:
            setattr(app, field, data[field])
    await db.commit()
    return ResponseBase(data={"id": str(app_id)}, message="აპი განახლდა")


@router.delete("/apps/{app_id}", response_model=ResponseBase[dict])
async def delete_studio_app(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("studio", "can_delete")),
):
    app = (await db.execute(select(StudioApp).where(
        StudioApp.id == app_id, StudioApp.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="აპი არ მოიძებნა")
    await db.delete(app)
    await db.commit()
    return ResponseBase(data={"id": str(app_id)}, message="აპი წაიშალა")


# ── Forms ─────────────────────────────────────────────────────────────────────

@router.get("/apps/{app_id}/forms", response_model=ResponseBase[list[dict]])
async def list_studio_forms(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("studio", "can_access")),
):
    rows = (await db.execute(
        select(StudioForm).where(
            StudioForm.app_id == app_id, StudioForm.company_id == current_user.company_id,
        ).options(selectinload(StudioForm.fields)).order_by(StudioForm.created_at)
    )).scalars().all()
    return ResponseBase(data=[_form_dict(f) for f in rows])


@router.post("/apps/{app_id}/forms", response_model=ResponseBase[dict], status_code=201)
async def create_studio_form(
    app_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("studio", "can_create")),
):
    app = (await db.execute(select(StudioApp).where(
        StudioApp.id == app_id, StudioApp.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="აპი არ მოიძებნა")
    form = StudioForm(
        company_id=current_user.company_id, app_id=app_id,
        name=data["name"], slug=data.get("slug") or data["name"].lower().replace(" ", "-"),
        layout=data.get("layout"),
    )
    db.add(form)
    await db.flush()
    for i, fd in enumerate(data.get("fields", [])):
        db.add(StudioField(
            company_id=current_user.company_id, form_id=form.id,
            label=fd["label"], field_key=fd.get("field_key") or fd["label"].lower().replace(" ", "_"),
            field_type=fd.get("field_type", "text"), required=bool(fd.get("required", False)),
            options=fd.get("options"), placeholder=fd.get("placeholder"), sort_order=i,
        ))
    await db.commit()
    await db.refresh(form)
    return ResponseBase(data={"id": str(form.id), "name": form.name}, message="ფორმა შეიქმნა")


@router.delete("/forms/{form_id}", response_model=ResponseBase[dict])
async def delete_studio_form(
    form_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("studio", "can_delete")),
):
    form = (await db.execute(select(StudioForm).where(
        StudioForm.id == form_id, StudioForm.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="ფორმა არ მოიძებნა")
    await db.delete(form)
    await db.commit()
    return ResponseBase(data={"id": str(form_id)}, message="ფორმა წაიშალა")


# ── Records (data) ────────────────────────────────────────────────────────────

@router.get("/forms/{form_id}/records", response_model=ResponseBase[PaginatedResponse[dict]])
async def list_studio_records(
    form_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("studio", "can_access")),
):
    form = (await db.execute(select(StudioForm).where(
        StudioForm.id == form_id, StudioForm.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="ფორმა არ მოიძებნა")
    filters = [StudioRecord.form_id == form_id, StudioRecord.company_id == current_user.company_id]
    total = (await db.execute(select(func.count(StudioRecord.id)).where(*filters))).scalar_one()
    rows = (await db.execute(
        select(StudioRecord).where(*filters)
        .order_by(StudioRecord.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[{
            "id": str(r.id), "form_id": str(r.form_id), "data": r.data,
            "created_by": str(r.created_by) if r.created_by else None,
            "created_at": r.created_at.isoformat(),
        } for r in rows],
    ))


@router.post("/forms/{form_id}/records", response_model=ResponseBase[dict], status_code=201)
async def create_studio_record(
    form_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("studio", "can_create")),
):
    form = (await db.execute(select(StudioForm).where(
        StudioForm.id == form_id, StudioForm.company_id == current_user.company_id,
    ).options(selectinload(StudioForm.fields)))).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="ფორმა არ მოიძებნა")

    # required-field validation
    payload = data.get("data", data)
    for fld in (form.fields or []):
        if fld.required and (fld.field_key not in payload or payload.get(fld.field_key) in (None, "")):
            raise HTTPException(status_code=422, detail=f"სავალდებულო ველი: {fld.label}")

    record = StudioRecord(
        company_id=current_user.company_id, form_id=form_id,
        data=payload, created_by=current_user.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return ResponseBase(data={"id": str(record.id)}, message="ჩანაწერი შეიქმნა")


@router.delete("/records/{record_id}", response_model=ResponseBase[dict])
async def delete_studio_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("studio", "can_delete")),
):
    record = (await db.execute(select(StudioRecord).where(
        StudioRecord.id == record_id, StudioRecord.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="ჩანაწერი არ მოიძებნა")
    await db.delete(record)
    await db.commit()
    return ResponseBase(data={"id": str(record_id)}, message="ჩანაწერი წაიშალა")

"""Configurable platform endpoints — Odoo-Studio-style builder."""
import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.platform import (
    CustomField,
    CustomFieldValue,
    ImportMapping,
    IndustryTemplate,
    ReportTemplate,
    WorkflowTemplate,
)
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/platform", tags=["პლატფორმა — კონფიგურაციადი"])

VALID_ENTITIES = {"client", "supplier", "order", "invoice", "product", "task", "project"}


def require_admin(user: User) -> None:
    if user.role not in (User.Role.ADMIN,):
        raise HTTPException(status_code=403, detail="ოპერაცია ხელმისაწვდომია მხოლოდ ადმინისთვის")


# ── Custom fields ─────────────────────────────────────────────────────────────

@router.get("/custom-fields", response_model=ResponseBase[list[dict]])
async def list_custom_fields(
    entity_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(CustomField).where(CustomField.company_id == current_user.company_id)
    if entity_type:
        query = query.where(CustomField.entity_type == entity_type)
    query = query.order_by(CustomField.entity_type, CustomField.sort_order)
    rows = (await db.execute(query)).scalars().all()
    return ResponseBase(data=[{
        "id": str(f.id), "entity_type": f.entity_type, "name": f.name,
        "label_ka": f.label_ka, "label_en": f.label_en, "field_type": f.field_type,
        "options": f.options, "required": f.required, "sort_order": f.sort_order,
        "is_active": f.is_active,
    } for f in rows])


@router.post("/custom-fields", response_model=ResponseBase[dict], status_code=201)
async def create_custom_field(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    entity_type = data.get("entity_type", "")
    if entity_type not in VALID_ENTITIES:
        raise HTTPException(status_code=422, detail=f"entity_type უნდა იყოს ერთ-ერთი: {', '.join(sorted(VALID_ENTITIES))}")
    name = data.get("name", "").strip()
    if not name or not data.get("label_ka"):
        raise HTTPException(status_code=422, detail="name და label_ka სავალდებულოა")
    field = CustomField(
        company_id=current_user.company_id,
        entity_type=entity_type,
        name=name,
        label_ka=data["label_ka"],
        label_en=data.get("label_en"),
        field_type=data.get("field_type", "text"),
        options=data.get("options"),
        required=bool(data.get("required", False)),
        sort_order=int(data.get("sort_order", 0)),
    )
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return ResponseBase(data={"id": str(field.id), "name": field.name}, message="ველი შეიქმნა")


@router.delete("/custom-fields/{field_id}", response_model=ResponseBase[dict])
async def delete_custom_field(
    field_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    field = (await db.execute(select(CustomField).where(
        CustomField.id == field_id, CustomField.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="ველი არ მოიძებნა")
    # remove stored values first (no cascade at DB level)
    from sqlalchemy import delete as sa_delete
    await db.execute(
        sa_delete(CustomFieldValue).where(CustomFieldValue.field_id == field.id)
    )
    await db.delete(field)
    await db.commit()
    return ResponseBase(data={"id": str(field_id)}, message="ველი წაიშალა")


@router.get("/custom-values", response_model=ResponseBase[list[dict]])
async def list_custom_values(
    entity_type: str,
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(CustomFieldValue).where(
            CustomFieldValue.company_id == current_user.company_id,
            CustomFieldValue.entity_type == entity_type,
            CustomFieldValue.entity_id == entity_id,
        )
    )).scalars().all()
    return ResponseBase(data=[{"field_id": str(v.field_id), "value": v.value} for v in rows])


@router.put("/custom-values/{entity_type}/{entity_id}", response_model=ResponseBase[dict])
async def set_custom_values(
    entity_type: str,
    entity_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set multiple custom field values for a record: {field_id: value}."""
    if entity_type not in VALID_ENTITIES:
        raise HTTPException(status_code=422, detail="entity_type არასწორია")
    for field_id_str, value in data.items():
        try:
            field_id = uuid.UUID(field_id_str)
        except ValueError:
            continue
        existing = (await db.execute(select(CustomFieldValue).where(
            CustomFieldValue.company_id == current_user.company_id,
            CustomFieldValue.field_id == field_id,
            CustomFieldValue.entity_type == entity_type,
            CustomFieldValue.entity_id == entity_id,
        ))).scalar_one_or_none()
        if existing:
            existing.value = {"v": value}
        else:
            db.add(CustomFieldValue(
                company_id=current_user.company_id,
                field_id=field_id,
                entity_type=entity_type,
                entity_id=entity_id,
                value={"v": value},
            ))
    await db.commit()
    return ResponseBase(data={"saved": len(data)}, message="მნიშვნელობები შეინახა")


# ── Workflow templates ────────────────────────────────────────────────────────

@router.get("/workflows", response_model=ResponseBase[list[dict]])
async def list_workflows(
    entity_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(WorkflowTemplate).where(WorkflowTemplate.company_id == current_user.company_id)
    if entity_type:
        query = query.where(WorkflowTemplate.entity_type == entity_type)
    rows = (await db.execute(query)).scalars().all()
    return ResponseBase(data=[{
        "id": str(w.id), "entity_type": w.entity_type, "name": w.name,
        "description": w.description, "steps": w.steps, "is_active": w.is_active,
    } for w in rows])


@router.post("/workflows", response_model=ResponseBase[dict], status_code=201)
async def create_workflow(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    entity_type = data.get("entity_type", "")
    if entity_type not in VALID_ENTITIES:
        raise HTTPException(status_code=422, detail="entity_type არასწორია")
    w = WorkflowTemplate(
        company_id=current_user.company_id,
        entity_type=entity_type,
        name=data.get("name", ""),
        description=data.get("description"),
        steps=data.get("steps", []),
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return ResponseBase(data={"id": str(w.id), "name": w.name}, message="ვორქფლოუ შეიქმნა")


@router.delete("/workflows/{workflow_id}", response_model=ResponseBase[dict])
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    w = (await db.execute(select(WorkflowTemplate).where(
        WorkflowTemplate.id == workflow_id, WorkflowTemplate.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="ვორქფლოუ არ მოიძებნა")
    await db.delete(w)
    await db.commit()
    return ResponseBase(data={"id": str(workflow_id)}, message="ვორქფლოუ წაიშალა")


# ── Report templates ──────────────────────────────────────────────────────────

@router.get("/reports", response_model=ResponseBase[list[dict]])
async def list_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(select(ReportTemplate).where(
        ReportTemplate.company_id == current_user.company_id,
    ))).scalars().all()
    return ResponseBase(data=[{
        "id": str(r.id), "name": r.name, "entity_type": r.entity_type,
        "columns": r.columns, "filters": r.filters, "sort_by": r.sort_by,
    } for r in rows])


@router.post("/reports", response_model=ResponseBase[dict], status_code=201)
async def create_report(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    r = ReportTemplate(
        company_id=current_user.company_id,
        name=data.get("name", ""),
        entity_type=data.get("entity_type", ""),
        columns=data.get("columns", []),
        filters=data.get("filters"),
        sort_by=data.get("sort_by"),
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return ResponseBase(data={"id": str(r.id), "name": r.name}, message="ანგარიში შეიქმნა")


@router.get("/reports/{report_id}/export", response_model=ResponseBase[dict])
async def export_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export report data as CSV (inline base64) based on the saved template."""
    r = (await db.execute(select(ReportTemplate).where(
        ReportTemplate.id == report_id, ReportTemplate.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="ანგარიში არ მოიძებნა")

    # collect rows from the target entity (generic columns only — custom fields via values)
    rows: list[dict] = []
    if r.entity_type == "client":
        from app.models.client import Client
        q = select(Client).where(Client.company_id == current_user.company_id)
        if r.filters and r.filters.get("status"):
            q = q.where(Client.status == r.filters["status"])
        for c in (await db.execute(q)).scalars().all():
            rows.append({"name": c.name, "identification_code": c.identification_code, "status": c.status})
    elif r.entity_type == "product":
        from app.models.product import Product
        for p in (await db.execute(select(Product).where(
            Product.company_id == current_user.company_id,
        ))).scalars().all():
            rows.append({"name": p.name, "sku": p.sku, "current_stock": float(p.current_stock)})
    elif r.entity_type == "order":
        from app.models.order import Order
        for o in (await db.execute(select(Order).where(
            Order.company_id == current_user.company_id,
        ))).scalars().all():
            rows.append({"order_number": o.order_number, "status": o.status, "total": float(o.total)})

    # build CSV from template columns
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([c.get("label", c.get("key", "")) for c in r.columns])
    for row in rows:
        writer.writerow([row.get(c.get("key", ""), "") for c in r.columns])
    csv_data = out.getvalue()
    return ResponseBase(data={"filename": f"{r.name}.csv", "csv": csv_data, "row_count": len(rows)})


# ── Import mappings ───────────────────────────────────────────────────────────

@router.get("/import-mappings", response_model=ResponseBase[list[dict]])
async def list_import_mappings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(select(ImportMapping).where(
        ImportMapping.company_id == current_user.company_id,
    ))).scalars().all()
    return ResponseBase(data=[{
        "id": str(m.id), "entity_type": m.entity_type, "name": m.name, "mapping": m.mapping,
    } for m in rows])


@router.post("/import-mappings", response_model=ResponseBase[dict], status_code=201)
async def create_import_mapping(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    m = ImportMapping(
        company_id=current_user.company_id,
        entity_type=data.get("entity_type", ""),
        name=data.get("name", ""),
        mapping=data.get("mapping", {}),
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return ResponseBase(data={"id": str(m.id), "name": m.name}, message="მეპინგი შეიქმნა")


@router.delete("/import-mappings/{mapping_id}", response_model=ResponseBase[dict])
async def delete_import_mapping(
    mapping_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    m = (await db.execute(select(ImportMapping).where(
        ImportMapping.id == mapping_id, ImportMapping.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="მეპინგი არ მოიძებნა")
    await db.delete(m)
    await db.commit()
    return ResponseBase(data={"id": str(mapping_id)}, message="მეპინგი წაიშალა")


# ── Industry templates ────────────────────────────────────────────────────────

@router.get("/industry-templates", response_model=ResponseBase[list[dict]])
async def list_industry_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(select(IndustryTemplate).order_by(IndustryTemplate.slug))).scalars().all()
    return ResponseBase(data=[{
        "id": str(t.id), "slug": t.slug, "name_ka": t.name_ka, "name_en": t.name_en,
        "description": t.description, "modules": t.modules, "custom_fields": t.custom_fields,
    } for t in rows])


@router.post("/industry-templates", response_model=ResponseBase[dict], status_code=201)
async def create_industry_template(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    slug = data.get("slug", "").strip().lower()
    if not slug:
        raise HTTPException(status_code=422, detail="slug სავალდებულოა")
    existing = (await db.execute(select(IndustryTemplate).where(IndustryTemplate.slug == slug))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="ასეთი ინდუსტრიის შაბლონი უკვე არსებობს")
    t = IndustryTemplate(
        slug=slug,
        name_ka=data.get("name_ka", ""),
        name_en=data.get("name_en"),
        description=data.get("description"),
        modules=data.get("modules", []),
        custom_fields=data.get("custom_fields"),
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return ResponseBase(data={"id": str(t.id), "slug": t.slug}, message="ინდუსტრიის შაბლონი შეიქმნა")

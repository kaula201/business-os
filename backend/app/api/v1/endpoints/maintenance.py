"""Maintenance & Repairs API — maintenance plans, maintenance orders, repair orders."""
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.maintenance import MaintenanceOrder, MaintenancePlan, RepairOrder
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/maintenance", tags=["Maintenance & Repairs"])


# ── Maintenance plans ───────────────────────────────────────────────


@router.get("/plans", response_model=ResponseBase[list[dict]])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenancePlan).where(MaintenancePlan.company_id == current_user.company_id).order_by(MaintenancePlan.name)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(p.id), "name": p.name, "asset_id": str(p.asset_id) if p.asset_id else None,
        "interval_days": p.interval_days, "next_due_at": p.next_due_at.isoformat() if p.next_due_at else None,
        "assigned_to": str(p.assigned_to) if p.assigned_to else None, "is_active": p.is_active,
    } for p in rows])


@router.post("/plans", response_model=ResponseBase[dict], status_code=201)
async def create_plan(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = MaintenancePlan(
        company_id=current_user.company_id,
        asset_id=data.get("asset_id"),
        name=data.get("name", ""),
        interval_days=int(data.get("interval_days", 30)),
        next_due_at=date.fromisoformat(data["next_due_at"]) if data.get("next_due_at") else None,
        assigned_to=data.get("assigned_to"),
        notes=data.get("notes"),
    )
    db.add(p)
    await db.flush()
    return ResponseBase(data={"id": str(p.id), "name": p.name}, message="მოვლის გეგმა შეიქმნა")


# ── Maintenance orders ───────────────────────────────────────────────


@router.get("/orders", response_model=ResponseBase[list[dict]])
async def list_orders(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenanceOrder).where(MaintenanceOrder.company_id == current_user.company_id)
    if status:
        q = q.where(MaintenanceOrder.status == status)
    rows = (await db.execute(q.order_by(MaintenanceOrder.created_at.desc()))).scalars().all()
    return ResponseBase(data=[{
        "id": str(o.id), "order_number": o.order_number, "asset_name": o.asset_name,
        "maintenance_type": o.maintenance_type, "priority": o.priority, "status": o.status,
        "scheduled_date": o.scheduled_date.isoformat() if o.scheduled_date else None,
        "cost_estimate": float(o.cost_estimate), "actual_cost": float(o.actual_cost),
        "downtime_hours": float(o.downtime_hours),
    } for o in rows])


@router.post("/orders", response_model=ResponseBase[dict], status_code=201)
async def create_order(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.api.v1.endpoints.purchase_orders import allocate_document_number
    number = await allocate_document_number(db, current_user.company_id, "maintenance_order", "MO")
    o = MaintenanceOrder(
        company_id=current_user.company_id,
        plan_id=data.get("plan_id"),
        order_number=number,
        asset_id=data.get("asset_id"),
        asset_name=data.get("asset_name"),
        maintenance_type=data.get("maintenance_type", "preventive"),
        priority=data.get("priority", "medium"),
        status=data.get("status", "draft"),
        scheduled_date=data.get("scheduled_date"),
        assigned_to=data.get("assigned_to"),
        cost_estimate=data.get("cost_estimate", 0),
        description=data.get("description"),
    )
    db.add(o)
    await db.flush()
    return ResponseBase(data={"id": str(o.id), "order_number": o.order_number}, message="მოვლის დავალება შეიქმნა")


@router.patch("/orders/{order_id}", response_model=ResponseBase[dict])
async def update_order(
    order_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    o = (await db.execute(
        select(MaintenanceOrder).where(MaintenanceOrder.id == order_id, MaintenanceOrder.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not o:
        raise HTTPException(status_code=404, detail="დავალება არ მოიძებნა")
    for field in ("status", "priority", "scheduled_date", "assigned_to", "actual_cost", "downtime_hours", "resolution_notes"):
        if field in data:
            setattr(o, field, data[field])
    if data.get("status") == "completed":
        o.completed_at = datetime.utcnow()
    await db.flush()
    return ResponseBase(data={"id": str(o.id), "status": o.status}, message="დავალება განახლდა")


# ── Repair orders ───────────────────────────────────────────────────


@router.get("/repairs", response_model=ResponseBase[list[dict]])
async def list_repairs(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(RepairOrder).where(RepairOrder.company_id == current_user.company_id)
    if status:
        q = q.where(RepairOrder.status == status)
    rows = (await db.execute(q.order_by(RepairOrder.created_at.desc()))).scalars().all()
    return ResponseBase(data=[{
        "id": str(r.id), "repair_number": r.repair_number, "client_id": str(r.client_id) if r.client_id else None,
        "product_id": str(r.product_id) if r.product_id else None, "serial_number": r.serial_number,
        "status": r.status, "issue_description": r.issue_description, "diagnosis": r.diagnosis,
        "estimated_cost": float(r.estimated_cost), "final_cost": float(r.final_cost),
        "warranty": r.warranty,
    } for r in rows])


@router.post("/repairs", response_model=ResponseBase[dict], status_code=201)
async def create_repair(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.api.v1.endpoints.purchase_orders import allocate_document_number
    number = await allocate_document_number(db, current_user.company_id, "repair_order", "RPR")
    r = RepairOrder(
        company_id=current_user.company_id,
        repair_number=number,
        client_id=data.get("client_id"),
        product_id=data.get("product_id"),
        serial_number=data.get("serial_number"),
        status=data.get("status", "received"),
        issue_description=data.get("issue_description"),
        estimated_cost=data.get("estimated_cost", 0),
        technician_id=data.get("technician_id"),
        warranty=data.get("warranty", False),
        received_at=datetime.utcnow(),
    )
    db.add(r)
    await db.flush()
    return ResponseBase(data={"id": str(r.id), "repair_number": r.repair_number}, message="რემონტი მიღებულია")


@router.patch("/repairs/{repair_id}", response_model=ResponseBase[dict])
async def update_repair(
    repair_id: uuid.UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = (await db.execute(
        select(RepairOrder).where(RepairOrder.id == repair_id, RepairOrder.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="რემონტი არ მოიძებნა")
    for field in ("status", "diagnosis", "estimated_cost", "final_cost", "technician_id", "notes"):
        if field in data:
            setattr(r, field, data[field])
    if data.get("status") == "completed":
        r.completed_at = datetime.utcnow()
    await db.flush()
    return ResponseBase(data={"id": str(r.id), "status": r.status}, message="რემონტი განახლდა")

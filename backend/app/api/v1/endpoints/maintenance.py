"""Maintenance & Repairs API — CMMS: assets, categories, locations, meters, requests, plans, orders, repairs."""
import uuid
from decimal import Decimal
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.maintenance import (
    MaintenanceAsset,
    MaintenanceAssetCategory,
    MaintenanceBudget,
    MaintenanceCertificate,
    MaintenanceChecklist,
    MaintenanceChecklistItem,
    MaintenanceContractor,
    MaintenanceCostRecord,
    MaintenanceIncident,
    MaintenanceLocation,
    MaintenanceMeter,
    MaintenanceNumberingConfig,
    MaintenanceOrder,
    MaintenancePart,
    MaintenancePartRequest,
    MaintenancePlan,
    MaintenancePriority,
    MaintenanceReliabilityMetric,
    MaintenanceRequest,
    MaintenanceSafetyInstruction,
    MaintenanceSLA,
    MaintenanceStatusConfig,
    MaintenanceTeam,
    MaintenanceTeamMember,
    MaintenanceTechnician,
    MaintenanceTool,
    MaintenanceToolIssue,
    MaintenanceWorkPermit,
    MaintenanceWorkType,
    RepairOrder,
)
from app.models.user import User
from app.schemas.common import ResponseBase
from app.schemas.maintenance import (
    MaintenanceAssetCategoryCreate,
    MaintenanceAssetCategoryResponse,
    MaintenanceAssetCreate,
    MaintenanceAssetResponse,
    MaintenanceAssetUpdate,
    MaintenanceCertificateCreate,
    MaintenanceCertificateResponse,
    MaintenanceContractorCreate,
    MaintenanceContractorResponse,
    MaintenanceContractorUpdate,
    MaintenanceLocationCreate,
    MaintenanceLocationResponse,
    MaintenanceMeterCreate,
    MaintenanceMeterResponse,
    MaintenanceMeterUpdate,
    MaintenanceOrderCreate,
    MaintenanceOrderResponse,
    MaintenanceOrderUpdate,
    MaintenancePartCreate,
    MaintenancePartRequestCreate,
    MaintenancePartRequestResponse,
    MaintenancePartRequestUpdate,
    MaintenancePartResponse,
    MaintenancePartUpdate,
    MaintenancePlanCreate,
    MaintenancePlanResponse,
    MaintenancePlanUpdate,
    MaintenanceRequestCreate,
    MaintenanceRequestResponse,
    MaintenanceRequestUpdate,
    MaintenanceSafetyInstructionCreate,
    MaintenanceSafetyInstructionResponse,
    MaintenanceWorkPermitCreate,
    MaintenanceWorkPermitResponse,
    MaintenanceWorkPermitUpdate,
    MaintenanceAnalyticsSummary,
    MaintenanceBudgetCreate,
    MaintenanceBudgetResponse,
    MaintenanceChecklistCreate,
    MaintenanceChecklistResponse,
    MaintenanceCostRecordCreate,
    MaintenanceCostRecordResponse,
    MaintenanceIncidentCreate,
    MaintenanceIncidentResponse,
    MaintenanceIncidentUpdate,
    MaintenanceNumberingConfigCreate,
    MaintenanceNumberingConfigResponse,
    MaintenancePriorityCreate,
    MaintenancePriorityResponse,
    MaintenanceReliabilityMetricCreate,
    MaintenanceReliabilityMetricResponse,
    MaintenanceSLACreate,
    MaintenanceSLAResponse,
    MaintenanceSLAUpdate,
    MaintenanceStatusConfigCreate,
    MaintenanceStatusConfigResponse,
    MaintenanceTeamCreate,
    MaintenanceTeamResponse,
    MaintenanceTeamUpdate,
    MaintenanceTechnicianCreate,
    MaintenanceTechnicianResponse,
    MaintenanceTechnicianUpdate,
    MaintenanceToolCreate,
    MaintenanceToolIssueCreate,
    MaintenanceToolIssueResponse,
    MaintenanceToolResponse,
    MaintenanceToolUpdate,
    MaintenanceWorkTypeCreate,
    MaintenanceWorkTypeResponse,
)

router = APIRouter(prefix="/maintenance", tags=["Maintenance & Repairs"])


# ── Asset categories ────────────────────────────────────────────────────────

@router.get("/asset-categories", response_model=ResponseBase[list[MaintenanceAssetCategoryResponse]])
async def list_asset_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceAssetCategory).where(MaintenanceAssetCategory.company_id == current_user.company_id).order_by(MaintenanceAssetCategory.name)
    )).scalars().all()
    return ResponseBase(data=[MaintenanceAssetCategoryResponse.model_validate(c) for c in rows])


@router.post("/asset-categories", response_model=ResponseBase[MaintenanceAssetCategoryResponse], status_code=201)
async def create_asset_category(
    data: MaintenanceAssetCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = MaintenanceAssetCategory(company_id=current_user.company_id, name=data.name.strip(), description=data.description)
    db.add(c)
    await db.flush()
    return ResponseBase(data=MaintenanceAssetCategoryResponse.model_validate(c), message="კატეგორია შეიქმნა")


# ── Locations ───────────────────────────────────────────────────────────────

@router.get("/locations", response_model=ResponseBase[list[MaintenanceLocationResponse]])
async def list_locations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceLocation).where(MaintenanceLocation.company_id == current_user.company_id).order_by(MaintenanceLocation.name)
    )).scalars().all()
    return ResponseBase(data=[MaintenanceLocationResponse.model_validate(l) for l in rows])


@router.post("/locations", response_model=ResponseBase[MaintenanceLocationResponse], status_code=201)
async def create_location(
    data: MaintenanceLocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    l = MaintenanceLocation(company_id=current_user.company_id, name=data.name.strip(), parent_id=data.parent_id, description=data.description)
    db.add(l)
    await db.flush()
    return ResponseBase(data=MaintenanceLocationResponse.model_validate(l), message="მდებარეობა შეიქმნა")


# ── Assets ──────────────────────────────────────────────────────────────────

def _asset_response(a: MaintenanceAsset, category_name: str | None = None, location_name: str | None = None) -> MaintenanceAssetResponse:
    return MaintenanceAssetResponse.model_validate(a).model_copy(update={"category_name": category_name, "location_name": location_name})


@router.get("/assets", response_model=ResponseBase[list[MaintenanceAssetResponse]])
async def list_assets(
    status: str | None = None,
    category_id: uuid.UUID | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenanceAsset).where(MaintenanceAsset.company_id == current_user.company_id)
    if status:
        q = q.where(MaintenanceAsset.status == status)
    if category_id:
        q = q.where(MaintenanceAsset.category_id == category_id)
    if search:
        term = f"%{search.strip()}%"
        q = q.where(or_(MaintenanceAsset.name.ilike(term), MaintenanceAsset.asset_code.ilike(term), MaintenanceAsset.serial_number.ilike(term)))
    rows = (await db.execute(q.order_by(MaintenanceAsset.asset_code))).scalars().all()

    cat_ids = {a.category_id for a in rows if a.category_id}
    loc_ids = {a.location_id for a in rows if a.location_id}
    cat_names = {row[0]: row[1] for row in (await db.execute(select(MaintenanceAssetCategory.id, MaintenanceAssetCategory.name).where(MaintenanceAssetCategory.id.in_(cat_ids)))).all()} if cat_ids else {}
    loc_names = {row[0]: row[1] for row in (await db.execute(select(MaintenanceLocation.id, MaintenanceLocation.name).where(MaintenanceLocation.id.in_(loc_ids)))).all()} if loc_ids else {}
    return ResponseBase(data=[_asset_response(a, cat_names.get(a.category_id), loc_names.get(a.location_id)) for a in rows])


@router.post("/assets", response_model=ResponseBase[MaintenanceAssetResponse], status_code=201)
async def create_asset(
    data: MaintenanceAssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dup = (await db.execute(select(MaintenanceAsset.id).where(
        MaintenanceAsset.company_id == current_user.company_id,
        MaintenanceAsset.asset_code == data.asset_code.strip(),
    ))).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="ამ კოდით აქტივი უკვე არსებობს")
    a = MaintenanceAsset(company_id=current_user.company_id, **data.model_dump())
    db.add(a)
    await db.flush()
    await db.refresh(a)
    cat_name = None
    loc_name = None
    if a.category_id:
        cat_name = (await db.execute(select(MaintenanceAssetCategory.name).where(MaintenanceAssetCategory.id == a.category_id))).scalar_one_or_none()
    if a.location_id:
        loc_name = (await db.execute(select(MaintenanceLocation.name).where(MaintenanceLocation.id == a.location_id))).scalar_one_or_none()
    return ResponseBase(data=_asset_response(a, cat_name, loc_name), message="აქტივი შეიქმნა")


@router.patch("/assets/{asset_id}", response_model=ResponseBase[MaintenanceAssetResponse])
async def update_asset(
    asset_id: uuid.UUID,
    data: MaintenanceAssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = (await db.execute(
        select(MaintenanceAsset).where(MaintenanceAsset.id == asset_id, MaintenanceAsset.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="აქტივი არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(a, field, value)
    await db.flush()
    await db.refresh(a)
    return ResponseBase(data=_asset_response(a), message="აქტივი განახლდა")


@router.delete("/assets/{asset_id}", response_model=ResponseBase)
async def delete_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = (await db.execute(
        select(MaintenanceAsset).where(MaintenanceAsset.id == asset_id, MaintenanceAsset.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="აქტივი არ მოიძებნა")
    await db.delete(a)
    await db.flush()
    return ResponseBase(message="აქტივი წაიშალა")


# ── Meters ─────────────────────────────────────────────────────────────────

@router.get("/meters", response_model=ResponseBase[list[MaintenanceMeterResponse]])
async def list_meters(
    asset_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenanceMeter).where(MaintenanceMeter.company_id == current_user.company_id)
    if asset_id:
        q = q.where(MaintenanceMeter.asset_id == asset_id)
    rows = (await db.execute(q.order_by(MaintenanceMeter.name))).scalars().all()
    asset_ids = {m.asset_id for m in rows}
    asset_names = {row[0]: row[1] for row in (await db.execute(select(MaintenanceAsset.id, MaintenanceAsset.name).where(MaintenanceAsset.id.in_(asset_ids)))).all()} if asset_ids else {}
    return ResponseBase(data=[MaintenanceMeterResponse.model_validate(m).model_copy(update={"asset_name": asset_names.get(m.asset_id)}) for m in rows])


@router.post("/meters", response_model=ResponseBase[MaintenanceMeterResponse], status_code=201)
async def create_meter(
    data: MaintenanceMeterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = (await db.execute(select(MaintenanceAsset.id).where(
        MaintenanceAsset.id == data.asset_id, MaintenanceAsset.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="აქტივი არ მოიძებნა")
    m = MaintenanceMeter(company_id=current_user.company_id, **data.model_dump())
    db.add(m)
    await db.flush()
    await db.refresh(m)
    asset_name = (await db.execute(select(MaintenanceAsset.name).where(MaintenanceAsset.id == m.asset_id))).scalar_one_or_none()
    return ResponseBase(data=MaintenanceMeterResponse.model_validate(m).model_copy(update={"asset_name": asset_name}), message="მრიცხველი შეიქმნა")


@router.patch("/meters/{meter_id}", response_model=ResponseBase[MaintenanceMeterResponse])
async def update_meter(
    meter_id: uuid.UUID,
    data: MaintenanceMeterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m = (await db.execute(
        select(MaintenanceMeter).where(MaintenanceMeter.id == meter_id, MaintenanceMeter.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="მრიცხველი არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    m.last_reading_at = utc_now()
    await db.flush()
    await db.refresh(m)
    return ResponseBase(data=MaintenanceMeterResponse.model_validate(m), message="მრიცხველი განახლდა")


# ── Requests ───────────────────────────────────────────────────────────────

@router.get("/requests", response_model=ResponseBase[list[MaintenanceRequestResponse]])
async def list_requests(
    status: str | None = None,
    priority: str | None = None,
    mine: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenanceRequest).where(MaintenanceRequest.company_id == current_user.company_id)
    if status:
        q = q.where(MaintenanceRequest.status == status)
    if priority:
        q = q.where(MaintenanceRequest.priority == priority)
    if mine:
        q = q.where(MaintenanceRequest.assigned_to == current_user.id)
    rows = (await db.execute(q.order_by(MaintenanceRequest.created_at.desc()))).scalars().all()
    asset_ids = {r.asset_id for r in rows if r.asset_id}
    asset_names = {row[0]: row[1] for row in (await db.execute(select(MaintenanceAsset.id, MaintenanceAsset.name).where(MaintenanceAsset.id.in_(asset_ids)))).all()} if asset_ids else {}
    return ResponseBase(data=[MaintenanceRequestResponse.model_validate(r).model_copy(update={"asset_name": asset_names.get(r.asset_id)}) for r in rows])


@router.post("/requests", response_model=ResponseBase[MaintenanceRequestResponse], status_code=201)
async def create_request(
    data: MaintenanceRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.api.v1.endpoints.purchase_orders import allocate_document_number
    number = await allocate_document_number(db, current_user.company_id, "maintenance_request", "MR")
    r = MaintenanceRequest(
        company_id=current_user.company_id,
        request_number=number,
        asset_id=data.asset_id,
        title=data.title.strip(),
        description=data.description,
        priority=data.priority,
        requested_by=data.requested_by or current_user.id,
        assigned_to=data.assigned_to,
        requested_date=data.requested_date or utc_now().date(),
    )
    db.add(r)
    await db.flush()
    await db.refresh(r)
    asset_name = None
    if r.asset_id:
        asset_name = (await db.execute(select(MaintenanceAsset.name).where(MaintenanceAsset.id == r.asset_id))).scalar_one_or_none()
    return ResponseBase(data=MaintenanceRequestResponse.model_validate(r).model_copy(update={"asset_name": asset_name}), message="მოთხოვნა შეიქმნა")


@router.patch("/requests/{request_id}", response_model=ResponseBase[MaintenanceRequestResponse])
async def update_request(
    request_id: uuid.UUID,
    data: MaintenanceRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = (await db.execute(
        select(MaintenanceRequest).where(MaintenanceRequest.id == request_id, MaintenanceRequest.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="მოთხოვნა არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(r, field, value)
    if data.status == "completed" and r.completed_at is None:
        r.completed_at = utc_now()
    await db.flush()
    await db.refresh(r)
    return ResponseBase(data=MaintenanceRequestResponse.model_validate(r), message="მოთხოვნა განახლდა")


# ── Maintenance plans ──────────────────────────────────────────────────────

@router.get("/plans", response_model=ResponseBase[list[MaintenancePlanResponse]])
async def list_plans(
    plan_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenancePlan).where(MaintenancePlan.company_id == current_user.company_id)
    if plan_type:
        q = q.where(MaintenancePlan.plan_type == plan_type)
    rows = (await db.execute(q.order_by(MaintenancePlan.name))).scalars().all()
    asset_ids = {p.asset_id for p in rows if p.asset_id}
    asset_names = {row[0]: row[1] for row in (await db.execute(select(MaintenanceAsset.id, MaintenanceAsset.name).where(MaintenanceAsset.id.in_(asset_ids)))).all()} if asset_ids else {}
    return ResponseBase(data=[MaintenancePlanResponse.model_validate(p).model_copy(update={"asset_name": asset_names.get(p.asset_id)}) for p in rows])


@router.post("/plans", response_model=ResponseBase[MaintenancePlanResponse], status_code=201)
async def create_plan(
    data: MaintenancePlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = MaintenancePlan(company_id=current_user.company_id, **data.model_dump())
    db.add(p)
    await db.flush()
    return ResponseBase(data=MaintenancePlanResponse.model_validate(p), message="მოვლის გეგმა შეიქმნა")


@router.patch("/plans/{plan_id}", response_model=ResponseBase[MaintenancePlanResponse])
async def update_plan(
    plan_id: uuid.UUID,
    data: MaintenancePlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = (await db.execute(
        select(MaintenancePlan).where(MaintenancePlan.id == plan_id, MaintenancePlan.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="გეგმა არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    await db.flush()
    await db.refresh(p)
    return ResponseBase(data=MaintenancePlanResponse.model_validate(p), message="გეგმა განახლდა")


# ── Maintenance orders ───────────────────────────────────────────────────────

@router.get("/orders", response_model=ResponseBase[list[MaintenanceOrderResponse]])
async def list_orders(
    status: str | None = None,
    maintenance_type: str | None = None,
    mine: bool = False,
    emergency: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenanceOrder).where(MaintenanceOrder.company_id == current_user.company_id)
    if status:
        q = q.where(MaintenanceOrder.status == status)
    if maintenance_type:
        q = q.where(MaintenanceOrder.maintenance_type == maintenance_type)
    if mine:
        q = q.where(MaintenanceOrder.assigned_to == current_user.id)
    if emergency is not None:
        q = q.where(MaintenanceOrder.is_emergency == emergency)
    rows = (await db.execute(q.order_by(MaintenanceOrder.created_at.desc()))).scalars().all()
    return ResponseBase(data=[MaintenanceOrderResponse.model_validate(o) for o in rows])


@router.post("/orders", response_model=ResponseBase[MaintenanceOrderResponse], status_code=201)
async def create_order(
    data: MaintenanceOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.api.v1.endpoints.purchase_orders import allocate_document_number
    number = await allocate_document_number(db, current_user.company_id, "maintenance_order", "MO")
    o = MaintenanceOrder(company_id=current_user.company_id, order_number=number, **data.model_dump())
    db.add(o)
    await db.flush()
    return ResponseBase(data=MaintenanceOrderResponse.model_validate(o), message="მოვლის დავალება შეიქმნა")


@router.patch("/orders/{order_id}", response_model=ResponseBase[MaintenanceOrderResponse])
async def update_order(
    order_id: uuid.UUID,
    data: MaintenanceOrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    o = (await db.execute(
        select(MaintenanceOrder).where(MaintenanceOrder.id == order_id, MaintenanceOrder.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not o:
        raise HTTPException(status_code=404, detail="დავალება არ მოიძებნა")
    before = o.status
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(o, field, value)
    if data.status == "in_progress" and o.started_at is None:
        o.started_at = utc_now()
    if data.status == "completed" and o.completed_at is None:
        o.completed_at = utc_now()
    if before != "completed" and o.status == "completed" and o.plan_id:
        plan = (await db.execute(select(MaintenancePlan).where(MaintenancePlan.id == o.plan_id))).scalar_one_or_none()
        if plan:
            plan.last_run_at = utc_now().date()
            plan.next_due_at = plan.last_run_at + __import__("datetime").timedelta(days=plan.interval_days)
    await db.flush()
    await db.refresh(o)
    return ResponseBase(data=MaintenanceOrderResponse.model_validate(o), message="დავალება განახლდა")


# ── Repair orders ───────────────────────────────────────────────────────────

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
        received_at=utc_now(),
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
        r.completed_at = utc_now()
    await db.flush()
    return ResponseBase(data={"id": str(r.id), "status": r.status}, message="რემონტი განახლდა")


# ── Phase 2: Resources — technicians, teams, contractors, SLA, certificates ──

@router.get("/technicians", response_model=ResponseBase[list[MaintenanceTechnicianResponse]])
async def list_technicians(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceTechnician).where(MaintenanceTechnician.company_id == current_user.company_id).order_by(MaintenanceTechnician.name)
    )).scalars().all()
    return ResponseBase(data=[MaintenanceTechnicianResponse.model_validate(t) for t in rows])


@router.post("/technicians", response_model=ResponseBase[MaintenanceTechnicianResponse], status_code=201)
async def create_technician(
    data: MaintenanceTechnicianCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = MaintenanceTechnician(company_id=current_user.company_id, **data.model_dump())
    db.add(t)
    await db.flush()
    return ResponseBase(data=MaintenanceTechnicianResponse.model_validate(t), message="ტექნიკოსი დაემატა")


@router.patch("/technicians/{technician_id}", response_model=ResponseBase[MaintenanceTechnicianResponse])
async def update_technician(
    technician_id: uuid.UUID,
    data: MaintenanceTechnicianUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = (await db.execute(
        select(MaintenanceTechnician).where(MaintenanceTechnician.id == technician_id, MaintenanceTechnician.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="ტექნიკოსი არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(t, field, value)
    await db.flush()
    await db.refresh(t)
    return ResponseBase(data=MaintenanceTechnicianResponse.model_validate(t), message="ტექნიკოსი განახლდა")


@router.get("/teams", response_model=ResponseBase[list[MaintenanceTeamResponse]])
async def list_teams(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceTeam).where(MaintenanceTeam.company_id == current_user.company_id).order_by(MaintenanceTeam.name)
    )).scalars().all()
    result = []
    for team in rows:
        count = (await db.execute(select(func.count(MaintenanceTeamMember.id)).where(MaintenanceTeamMember.team_id == team.id))).scalar_one()
        result.append(MaintenanceTeamResponse.model_validate(team).model_copy(update={"member_count": count}))
    return ResponseBase(data=result)


@router.post("/teams", response_model=ResponseBase[MaintenanceTeamResponse], status_code=201)
async def create_team(
    data: MaintenanceTeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = MaintenanceTeam(company_id=current_user.company_id, **data.model_dump())
    db.add(t)
    await db.flush()
    return ResponseBase(data=MaintenanceTeamResponse.model_validate(t), message="გუნდი შეიქმნა")


@router.post("/teams/{team_id}/members", response_model=ResponseBase[dict], status_code=201)
async def add_team_member(
    team_id: uuid.UUID,
    technician_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    team = (await db.execute(select(MaintenanceTeam.id).where(
        MaintenanceTeam.id == team_id, MaintenanceTeam.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="გუნდი არ მოიძებნა")
    db.add(MaintenanceTeamMember(team_id=team_id, technician_id=technician_id))
    await db.flush()
    return ResponseBase(message="წევრი დაემატა")


@router.delete("/teams/{team_id}/members/{technician_id}", response_model=ResponseBase)
async def remove_team_member(
    team_id: uuid.UUID,
    technician_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m = (await db.execute(select(MaintenanceTeamMember).where(
        MaintenanceTeamMember.team_id == team_id, MaintenanceTeamMember.technician_id == technician_id,
    ))).scalar_one_or_none()
    if m:
        await db.delete(m)
        await db.flush()
    return ResponseBase(message="წევრი ამოღებულია")


@router.get("/contractors", response_model=ResponseBase[list[MaintenanceContractorResponse]])
async def list_contractors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceContractor).where(MaintenanceContractor.company_id == current_user.company_id).order_by(MaintenanceContractor.name)
    )).scalars().all()
    return ResponseBase(data=[MaintenanceContractorResponse.model_validate(c) for c in rows])


@router.post("/contractors", response_model=ResponseBase[MaintenanceContractorResponse], status_code=201)
async def create_contractor(
    data: MaintenanceContractorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = MaintenanceContractor(company_id=current_user.company_id, **data.model_dump())
    db.add(c)
    await db.flush()
    return ResponseBase(data=MaintenanceContractorResponse.model_validate(c), message="კონტრაქტორი დაემატა")


@router.patch("/contractors/{contractor_id}", response_model=ResponseBase[MaintenanceContractorResponse])
async def update_contractor(
    contractor_id: uuid.UUID,
    data: MaintenanceContractorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = (await db.execute(
        select(MaintenanceContractor).where(MaintenanceContractor.id == contractor_id, MaintenanceContractor.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="კონტრაქტორი არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    await db.flush()
    await db.refresh(c)
    return ResponseBase(data=MaintenanceContractorResponse.model_validate(c), message="კონტრაქტორი განახლდა")


@router.get("/slas", response_model=ResponseBase[list[MaintenanceSLAResponse]])
async def list_slas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceSLA).where(MaintenanceSLA.company_id == current_user.company_id).order_by(MaintenanceSLA.name)
    )).scalars().all()
    contractor_ids = {s.contractor_id for s in rows if s.contractor_id}
    contractor_names = {row[0]: row[1] for row in (await db.execute(
        select(MaintenanceContractor.id, MaintenanceContractor.name).where(MaintenanceContractor.id.in_(contractor_ids))
    )).all()} if contractor_ids else {}
    return ResponseBase(data=[MaintenanceSLAResponse.model_validate(s).model_copy(update={"contractor_name": contractor_names.get(s.contractor_id)}) for s in rows])


@router.post("/slas", response_model=ResponseBase[MaintenanceSLAResponse], status_code=201)
async def create_sla(
    data: MaintenanceSLACreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = MaintenanceSLA(company_id=current_user.company_id, **data.model_dump())
    db.add(s)
    await db.flush()
    await db.refresh(s)
    contractor_name = None
    if s.contractor_id:
        contractor_name = (await db.execute(select(MaintenanceContractor.name).where(MaintenanceContractor.id == s.contractor_id))).scalar_one_or_none()
    return ResponseBase(data=MaintenanceSLAResponse.model_validate(s).model_copy(update={"contractor_name": contractor_name}), message="SLA შეიქმნა")


@router.patch("/slas/{sla_id}", response_model=ResponseBase[MaintenanceSLAResponse])
async def update_sla(
    sla_id: uuid.UUID,
    data: MaintenanceSLAUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = (await db.execute(
        select(MaintenanceSLA).where(MaintenanceSLA.id == sla_id, MaintenanceSLA.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="SLA არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    await db.flush()
    await db.refresh(s)
    return ResponseBase(data=MaintenanceSLAResponse.model_validate(s), message="SLA განახლდა")


@router.get("/certificates", response_model=ResponseBase[list[MaintenanceCertificateResponse]])
async def list_certificates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceCertificate).where(MaintenanceCertificate.company_id == current_user.company_id).order_by(MaintenanceCertificate.name)
    )).scalars().all()
    tech_ids = {c.technician_id for c in rows}
    tech_names = {row[0]: row[1] for row in (await db.execute(
        select(MaintenanceTechnician.id, MaintenanceTechnician.name).where(MaintenanceTechnician.id.in_(tech_ids))
    )).all()} if tech_ids else {}
    return ResponseBase(data=[MaintenanceCertificateResponse.model_validate(c).model_copy(update={"technician_name": tech_names.get(c.technician_id)}) for c in rows])


@router.post("/certificates", response_model=ResponseBase[MaintenanceCertificateResponse], status_code=201)
async def create_certificate(
    data: MaintenanceCertificateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tech = (await db.execute(select(MaintenanceTechnician.id).where(
        MaintenanceTechnician.id == data.technician_id, MaintenanceTechnician.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not tech:
        raise HTTPException(status_code=404, detail="ტექნიკოსი არ მოიძებნა")
    c = MaintenanceCertificate(company_id=current_user.company_id, **data.model_dump())
    db.add(c)
    await db.flush()
    await db.refresh(c)
    tech_name = (await db.execute(select(MaintenanceTechnician.name).where(MaintenanceTechnician.id == c.technician_id))).scalar_one_or_none()
    return ResponseBase(data=MaintenanceCertificateResponse.model_validate(c).model_copy(update={"technician_name": tech_name}), message="სერტიფიკატი დაემატა")


# ── Phase 3: Parts & Tools ───────────────────────────────────────────────────

@router.get("/parts", response_model=ResponseBase[list[MaintenancePartResponse]])
async def list_parts(
    low: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenancePart).where(MaintenancePart.company_id == current_user.company_id)
    rows = (await db.execute(q.order_by(MaintenancePart.part_code))).scalars().all()
    result = []
    for p in rows:
        is_low = p.quantity_on_hand <= p.reorder_level
        if low and not is_low:
            continue
        result.append(MaintenancePartResponse.model_validate(p).model_copy(update={"is_low": is_low}))
    return ResponseBase(data=result)


@router.post("/parts", response_model=ResponseBase[MaintenancePartResponse], status_code=201)
async def create_part(
    data: MaintenancePartCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dup = (await db.execute(select(MaintenancePart.id).where(
        MaintenancePart.company_id == current_user.company_id,
        MaintenancePart.part_code == data.part_code.strip(),
    ))).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="ამ კოდით ნაწილი უკვე არსებობს")
    p = MaintenancePart(company_id=current_user.company_id, **data.model_dump())
    db.add(p)
    await db.flush()
    await db.refresh(p)
    return ResponseBase(data=MaintenancePartResponse.model_validate(p).model_copy(update={"is_low": p.quantity_on_hand <= p.reorder_level}), message="ნაწილი დაემატა")


@router.patch("/parts/{part_id}", response_model=ResponseBase[MaintenancePartResponse])
async def update_part(
    part_id: uuid.UUID,
    data: MaintenancePartUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = (await db.execute(
        select(MaintenancePart).where(MaintenancePart.id == part_id, MaintenancePart.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="ნაწილი არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    await db.flush()
    await db.refresh(p)
    return ResponseBase(data=MaintenancePartResponse.model_validate(p).model_copy(update={"is_low": p.quantity_on_hand <= p.reorder_level}), message="ნაწილი განახლდა")


@router.get("/part-requests", response_model=ResponseBase[list[MaintenancePartRequestResponse]])
async def list_part_requests(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenancePartRequest).where(MaintenancePartRequest.company_id == current_user.company_id)
    if status:
        q = q.where(MaintenancePartRequest.status == status)
    rows = (await db.execute(q.order_by(MaintenancePartRequest.requested_at.desc()))).scalars().all()
    part_ids = {r.part_id for r in rows}
    part_info = {row[0]: (row[1], row[2]) for row in (await db.execute(
        select(MaintenancePart.id, MaintenancePart.name, MaintenancePart.part_code).where(MaintenancePart.id.in_(part_ids))
    )).all()} if part_ids else {}
    result = []
    for r in rows:
        name, code = part_info.get(r.part_id, (None, None))
        result.append(MaintenancePartRequestResponse.model_validate(r).model_copy(update={"part_name": name, "part_code": code}))
    return ResponseBase(data=result)


@router.post("/part-requests", response_model=ResponseBase[MaintenancePartRequestResponse], status_code=201)
async def create_part_request(
    data: MaintenancePartRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    part = (await db.execute(select(MaintenancePart).where(
        MaintenancePart.id == data.part_id, MaintenancePart.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="ნაწილი არ მოიძებნა")
    r = MaintenancePartRequest(company_id=current_user.company_id, requested_by=current_user.id, **data.model_dump())
    db.add(r)
    await db.flush()
    await db.refresh(r)
    return ResponseBase(data=MaintenancePartRequestResponse.model_validate(r).model_copy(update={"part_name": part.name, "part_code": part.part_code}), message="მოთხოვნა შეიქმნა")


@router.patch("/part-requests/{request_id}", response_model=ResponseBase[MaintenancePartRequestResponse])
async def update_part_request(
    request_id: uuid.UUID,
    data: MaintenancePartRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = (await db.execute(
        select(MaintenancePartRequest).where(MaintenancePartRequest.id == request_id, MaintenancePartRequest.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="მოთხოვნა არ მოიძებნა")
    if data.status == "issued" and r.status != "issued":
        r.issued_at = utc_now()
        part = (await db.execute(select(MaintenancePart).where(MaintenancePart.id == r.part_id))).scalar_one_or_none()
        if part:
            part.quantity_on_hand = part.quantity_on_hand - r.quantity
    r.status = data.status or r.status
    await db.flush()
    await db.refresh(r)
    part = (await db.execute(select(MaintenancePart).where(MaintenancePart.id == r.part_id))).scalar_one_or_none()
    return ResponseBase(data=MaintenancePartRequestResponse.model_validate(r).model_copy(update={"part_name": part.name if part else None, "part_code": part.part_code if part else None}), message="მოთხოვნა განახლდა")


@router.get("/tools", response_model=ResponseBase[list[MaintenanceToolResponse]])
async def list_tools(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceTool).where(MaintenanceTool.company_id == current_user.company_id).order_by(MaintenanceTool.tool_code)
    )).scalars().all()
    return ResponseBase(data=[MaintenanceToolResponse.model_validate(t) for t in rows])


@router.post("/tools", response_model=ResponseBase[MaintenanceToolResponse], status_code=201)
async def create_tool(
    data: MaintenanceToolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dup = (await db.execute(select(MaintenanceTool.id).where(
        MaintenanceTool.company_id == current_user.company_id,
        MaintenanceTool.tool_code == data.tool_code.strip(),
    ))).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="ამ კოდით ხელსაწყო უკვე არსებობს")
    t = MaintenanceTool(company_id=current_user.company_id, available=data.quantity, **data.model_dump())
    db.add(t)
    await db.flush()
    return ResponseBase(data=MaintenanceToolResponse.model_validate(t), message="ხელსაწყო დაემატა")


@router.patch("/tools/{tool_id}", response_model=ResponseBase[MaintenanceToolResponse])
async def update_tool(
    tool_id: uuid.UUID,
    data: MaintenanceToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = (await db.execute(
        select(MaintenanceTool).where(MaintenanceTool.id == tool_id, MaintenanceTool.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="ხელსაწყო არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(t, field, value)
    await db.flush()
    await db.refresh(t)
    return ResponseBase(data=MaintenanceToolResponse.model_validate(t), message="ხელსაწყო განახლდა")


@router.get("/tool-issues", response_model=ResponseBase[list[MaintenanceToolIssueResponse]])
async def list_tool_issues(
    open_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenanceToolIssue).where(MaintenanceToolIssue.company_id == current_user.company_id)
    if open_only:
        q = q.where(MaintenanceToolIssue.returned_at.is_(None))
    rows = (await db.execute(q.order_by(MaintenanceToolIssue.issued_at.desc()))).scalars().all()
    tool_ids = {i.tool_id for i in rows}
    tech_ids = {i.technician_id for i in rows}
    tool_names = {row[0]: row[1] for row in (await db.execute(
        select(MaintenanceTool.id, MaintenanceTool.name).where(MaintenanceTool.id.in_(tool_ids))
    )).all()} if tool_ids else {}
    tech_names = {row[0]: row[1] for row in (await db.execute(
        select(MaintenanceTechnician.id, MaintenanceTechnician.name).where(MaintenanceTechnician.id.in_(tech_ids))
    )).all()} if tech_ids else {}
    return ResponseBase(data=[MaintenanceToolIssueResponse.model_validate(i).model_copy(update={"tool_name": tool_names.get(i.tool_id), "technician_name": tech_names.get(i.technician_id)}) for i in rows])


@router.post("/tool-issues", response_model=ResponseBase[MaintenanceToolIssueResponse], status_code=201)
async def issue_tool(
    data: MaintenanceToolIssueCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tool = (await db.execute(select(MaintenanceTool).where(
        MaintenanceTool.id == data.tool_id, MaintenanceTool.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="ხელსაწყო არ მოიძებნა")
    if tool.available <= 0:
        raise HTTPException(status_code=400, detail="ხელსაწყო არ არის ხელმისაწვდომი")
    tech = (await db.execute(select(MaintenanceTechnician.id).where(
        MaintenanceTechnician.id == data.technician_id, MaintenanceTechnician.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not tech:
        raise HTTPException(status_code=404, detail="ტექნიკოსი არ მოიძებნა")
    tool.available = tool.available - 1
    if tool.available == 0:
        tool.status = "issued"
    i = MaintenanceToolIssue(company_id=current_user.company_id, **data.model_dump())
    db.add(i)
    await db.flush()
    await db.refresh(i)
    tech_name = (await db.execute(select(MaintenanceTechnician.name).where(MaintenanceTechnician.id == i.technician_id))).scalar_one_or_none()
    return ResponseBase(data=MaintenanceToolIssueResponse.model_validate(i).model_copy(update={"tool_name": tool.name, "technician_name": tech_name}), message="ხელსაწყო გაიცა")


@router.post("/tool-issues/{issue_id}/return", response_model=ResponseBase[MaintenanceToolIssueResponse])
async def return_tool(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    i = (await db.execute(
        select(MaintenanceToolIssue).where(MaintenanceToolIssue.id == issue_id, MaintenanceToolIssue.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not i:
        raise HTTPException(status_code=404, detail="გაცემა არ მოიძებნა")
    if i.returned_at is None:
        i.returned_at = utc_now()
        tool = (await db.execute(select(MaintenanceTool).where(MaintenanceTool.id == i.tool_id))).scalar_one_or_none()
        if tool:
            tool.available = tool.available + 1
            if tool.available > 0:
                tool.status = "available"
    await db.flush()
    await db.refresh(i)
    return ResponseBase(data=MaintenanceToolIssueResponse.model_validate(i), message="ხელსაწყო დაბრუნდა")


# ── Phase 4: Planning & Safety ───────────────────────────────────────────────

@router.get("/safety-instructions", response_model=ResponseBase[list[MaintenanceSafetyInstructionResponse]])
async def list_safety_instructions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceSafetyInstruction).where(MaintenanceSafetyInstruction.company_id == current_user.company_id).order_by(MaintenanceSafetyInstruction.title)
    )).scalars().all()
    return ResponseBase(data=[MaintenanceSafetyInstructionResponse.model_validate(s) for s in rows])


@router.post("/safety-instructions", response_model=ResponseBase[MaintenanceSafetyInstructionResponse], status_code=201)
async def create_safety_instruction(
    data: MaintenanceSafetyInstructionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = MaintenanceSafetyInstruction(company_id=current_user.company_id, **data.model_dump())
    db.add(s)
    await db.flush()
    return ResponseBase(data=MaintenanceSafetyInstructionResponse.model_validate(s), message="ინსტრუქცია დაემატა")


@router.get("/work-permits", response_model=ResponseBase[list[MaintenanceWorkPermitResponse]])
async def list_work_permits(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenanceWorkPermit).where(MaintenanceWorkPermit.company_id == current_user.company_id)
    if status:
        q = q.where(MaintenanceWorkPermit.status == status)
    rows = (await db.execute(q.order_by(MaintenanceWorkPermit.created_at.desc()))).scalars().all()
    order_ids = {w.order_id for w in rows if w.order_id}
    order_nums = {row[0]: row[1] for row in (await db.execute(
        select(MaintenanceOrder.id, MaintenanceOrder.order_number).where(MaintenanceOrder.id.in_(order_ids))
    )).all()} if order_ids else {}
    return ResponseBase(data=[MaintenanceWorkPermitResponse.model_validate(w).model_copy(update={"order_number": order_nums.get(w.order_id)}) for w in rows])


@router.post("/work-permits", response_model=ResponseBase[MaintenanceWorkPermitResponse], status_code=201)
async def create_work_permit(
    data: MaintenanceWorkPermitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dup = (await db.execute(select(MaintenanceWorkPermit.id).where(
        MaintenanceWorkPermit.company_id == current_user.company_id,
        MaintenanceWorkPermit.permit_number == data.permit_number.strip(),
    ))).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="ამ ნომრით ნებართვა უკვე არსებობს")
    w = MaintenanceWorkPermit(company_id=current_user.company_id, **data.model_dump())
    db.add(w)
    await db.flush()
    await db.refresh(w)
    order_number = None
    if w.order_id:
        order_number = (await db.execute(select(MaintenanceOrder.order_number).where(MaintenanceOrder.id == w.order_id))).scalar_one_or_none()
    return ResponseBase(data=MaintenanceWorkPermitResponse.model_validate(w).model_copy(update={"order_number": order_number}), message="ნებართვა შეიქმნა")


@router.patch("/work-permits/{permit_id}", response_model=ResponseBase[MaintenanceWorkPermitResponse])
async def update_work_permit(
    permit_id: uuid.UUID,
    data: MaintenanceWorkPermitUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    w = (await db.execute(
        select(MaintenanceWorkPermit).where(MaintenanceWorkPermit.id == permit_id, MaintenanceWorkPermit.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="ნებართვა არ მოიძებნა")
    if data.status == "approved" and w.status != "approved":
        w.issued_at = utc_now()
        w.approved_by = current_user.id
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(w, field, value)
    await db.flush()
    await db.refresh(w)
    order_number = None
    if w.order_id:
        order_number = (await db.execute(select(MaintenanceOrder.order_number).where(MaintenanceOrder.id == w.order_id))).scalar_one_or_none()
    return ResponseBase(data=MaintenanceWorkPermitResponse.model_validate(w).model_copy(update={"order_number": order_number}), message="ნებართვა განახლდა")


@router.get("/checklists", response_model=ResponseBase[list[MaintenanceChecklistResponse]])
async def list_checklists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceChecklist).where(MaintenanceChecklist.company_id == current_user.company_id).order_by(MaintenanceChecklist.name)
    )).scalars().all()
    ids = [c.id for c in rows]
    counts = {row[0]: row[1] for row in (await db.execute(
        select(MaintenanceChecklistItem.checklist_id, func.count(MaintenanceChecklistItem.id)).where(MaintenanceChecklistItem.checklist_id.in_(ids)).group_by(MaintenanceChecklistItem.checklist_id)
    )).all()} if ids else {}
    return ResponseBase(data=[MaintenanceChecklistResponse.model_validate(c).model_copy(update={"item_count": counts.get(c.id, 0)}) for c in rows])


@router.post("/checklists", response_model=ResponseBase[MaintenanceChecklistResponse], status_code=201)
async def create_checklist(
    data: MaintenanceChecklistCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = MaintenanceChecklist(company_id=current_user.company_id, name=data.name, category=data.category, is_mandatory=data.is_mandatory)
    db.add(c)
    await db.flush()
    for idx, item_text in enumerate(data.items or []):
        if item_text.strip():
            db.add(MaintenanceChecklistItem(company_id=current_user.company_id, checklist_id=c.id, text=item_text.strip(), sort_order=idx))
    await db.flush()
    return ResponseBase(data=MaintenanceChecklistResponse.model_validate(c).model_copy(update={"item_count": len(data.items or [])}), message="ჩეკლისტი შეიქმნა")


@router.get("/incidents", response_model=ResponseBase[list[MaintenanceIncidentResponse]])
async def list_incidents(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenanceIncident).where(MaintenanceIncident.company_id == current_user.company_id)
    if status:
        q = q.where(MaintenanceIncident.status == status)
    rows = (await db.execute(q.order_by(MaintenanceIncident.created_at.desc()))).scalars().all()
    return ResponseBase(data=[MaintenanceIncidentResponse.model_validate(i) for i in rows])


@router.post("/incidents", response_model=ResponseBase[MaintenanceIncidentResponse], status_code=201)
async def create_incident(
    data: MaintenanceIncidentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dup = (await db.execute(select(MaintenanceIncident.id).where(
        MaintenanceIncident.company_id == current_user.company_id,
        MaintenanceIncident.incident_number == data.incident_number.strip(),
    ))).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="ამ ნომრით ინციდენტი უკვე არსებობს")
    i = MaintenanceIncident(company_id=current_user.company_id, reported_by=current_user.id, **data.model_dump())
    db.add(i)
    await db.flush()
    return ResponseBase(data=MaintenanceIncidentResponse.model_validate(i), message="ინციდენტი დაფიქსირდა")


@router.patch("/incidents/{incident_id}", response_model=ResponseBase[MaintenanceIncidentResponse])
async def update_incident(
    incident_id: uuid.UUID,
    data: MaintenanceIncidentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    i = (await db.execute(
        select(MaintenanceIncident).where(MaintenanceIncident.id == incident_id, MaintenanceIncident.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not i:
        raise HTTPException(status_code=404, detail="ინციდენტი არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(i, field, value)
    await db.flush()
    await db.refresh(i)
    return ResponseBase(data=MaintenanceIncidentResponse.model_validate(i), message="ინციდენტი განახლდა")


# ── Phase 5: Costs & Analytics ───────────────────────────────────────────────

@router.get("/cost-records", response_model=ResponseBase[list[MaintenanceCostRecordResponse]])
async def list_cost_records(
    cost_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenanceCostRecord).where(MaintenanceCostRecord.company_id == current_user.company_id)
    if cost_type:
        q = q.where(MaintenanceCostRecord.cost_type == cost_type)
    rows = (await db.execute(q.order_by(MaintenanceCostRecord.incurred_at.desc()))).scalars().all()
    order_ids = {c.order_id for c in rows if c.order_id}
    asset_ids = {c.asset_id for c in rows if c.asset_id}
    order_nums = {row[0]: row[1] for row in (await db.execute(
        select(MaintenanceOrder.id, MaintenanceOrder.order_number).where(MaintenanceOrder.id.in_(order_ids))
    )).all()} if order_ids else {}
    asset_names = {row[0]: row[1] for row in (await db.execute(
        select(MaintenanceAsset.id, MaintenanceAsset.name).where(MaintenanceAsset.id.in_(asset_ids))
    )).all()} if asset_ids else {}
    return ResponseBase(data=[MaintenanceCostRecordResponse.model_validate(c).model_copy(update={"order_number": order_nums.get(c.order_id), "asset_name": asset_names.get(c.asset_id)}) for c in rows])


@router.post("/cost-records", response_model=ResponseBase[MaintenanceCostRecordResponse], status_code=201)
async def create_cost_record(
    data: MaintenanceCostRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = MaintenanceCostRecord(company_id=current_user.company_id, **data.model_dump())
    db.add(c)
    await db.flush()
    await db.refresh(c)
    order_number = None
    asset_name = None
    if c.order_id:
        order_number = (await db.execute(select(MaintenanceOrder.order_number).where(MaintenanceOrder.id == c.order_id))).scalar_one_or_none()
    if c.asset_id:
        asset_name = (await db.execute(select(MaintenanceAsset.name).where(MaintenanceAsset.id == c.asset_id))).scalar_one_or_none()
    return ResponseBase(data=MaintenanceCostRecordResponse.model_validate(c).model_copy(update={"order_number": order_number, "asset_name": asset_name}), message="ხარჯი დაემატა")


@router.get("/budgets", response_model=ResponseBase[list[MaintenanceBudgetResponse]])
async def list_budgets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceBudget).where(MaintenanceBudget.company_id == current_user.company_id).order_by(MaintenanceBudget.period_start.desc())
    )).scalars().all()
    result = []
    for b in rows:
        spent = (await db.execute(
            select(func.coalesce(func.sum(MaintenanceCostRecord.amount), 0)).where(
                MaintenanceCostRecord.company_id == current_user.company_id,
                MaintenanceCostRecord.incurred_at >= datetime.combine(b.period_start, datetime.min.time()),
                MaintenanceCostRecord.incurred_at <= datetime.combine(b.period_end, datetime.max.time()),
            )
        )).scalar_one()
        result.append(MaintenanceBudgetResponse.model_validate(b).model_copy(update={"spent_amount": Decimal(str(spent))}))
    return ResponseBase(data=result)


@router.post("/budgets", response_model=ResponseBase[MaintenanceBudgetResponse], status_code=201)
async def create_budget(
    data: MaintenanceBudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    b = MaintenanceBudget(company_id=current_user.company_id, **data.model_dump())
    db.add(b)
    await db.flush()
    return ResponseBase(data=MaintenanceBudgetResponse.model_validate(b), message="ბიუჯეტი შეიქმნა")


@router.get("/reliability-metrics", response_model=ResponseBase[list[MaintenanceReliabilityMetricResponse]])
async def list_reliability_metrics(
    asset_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(MaintenanceReliabilityMetric).where(MaintenanceReliabilityMetric.company_id == current_user.company_id)
    if asset_id:
        q = q.where(MaintenanceReliabilityMetric.asset_id == asset_id)
    rows = (await db.execute(q.order_by(MaintenanceReliabilityMetric.period_start.desc()))).scalars().all()
    asset_ids = {m.asset_id for m in rows}
    asset_names = {row[0]: row[1] for row in (await db.execute(
        select(MaintenanceAsset.id, MaintenanceAsset.name).where(MaintenanceAsset.id.in_(asset_ids))
    )).all()} if asset_ids else {}
    return ResponseBase(data=[MaintenanceReliabilityMetricResponse.model_validate(m).model_copy(update={"asset_name": asset_names.get(m.asset_id)}) for m in rows])


@router.post("/reliability-metrics", response_model=ResponseBase[MaintenanceReliabilityMetricResponse], status_code=201)
async def create_reliability_metric(
    data: MaintenanceReliabilityMetricCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = (await db.execute(select(MaintenanceAsset.id).where(
        MaintenanceAsset.id == data.asset_id, MaintenanceAsset.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="აქტივი არ მოიძებნა")
    m = MaintenanceReliabilityMetric(company_id=current_user.company_id, **data.model_dump())
    db.add(m)
    await db.flush()
    await db.refresh(m)
    asset_name = (await db.execute(select(MaintenanceAsset.name).where(MaintenanceAsset.id == m.asset_id))).scalar_one_or_none()
    return ResponseBase(data=MaintenanceReliabilityMetricResponse.model_validate(m).model_copy(update={"asset_name": asset_name}), message="მეტრიკა დაემატა")


@router.get("/analytics/summary", response_model=ResponseBase[MaintenanceAnalyticsSummary])
async def analytics_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cid = current_user.company_id
    total = (await db.execute(select(func.coalesce(func.sum(MaintenanceCostRecord.amount), 0)).where(MaintenanceCostRecord.company_id == cid))).scalar_one()
    labor = (await db.execute(select(func.coalesce(func.sum(MaintenanceCostRecord.amount), 0)).where(MaintenanceCostRecord.company_id == cid, MaintenanceCostRecord.cost_type == "labor"))).scalar_one()
    parts = (await db.execute(select(func.coalesce(func.sum(MaintenanceCostRecord.amount), 0)).where(MaintenanceCostRecord.company_id == cid, MaintenanceCostRecord.cost_type == "parts"))).scalar_one()
    contractor = (await db.execute(select(func.coalesce(func.sum(MaintenanceCostRecord.amount), 0)).where(MaintenanceCostRecord.company_id == cid, MaintenanceCostRecord.cost_type == "contractor"))).scalar_one()
    other = (await db.execute(select(func.coalesce(func.sum(MaintenanceCostRecord.amount), 0)).where(MaintenanceCostRecord.company_id == cid, MaintenanceCostRecord.cost_type == "other"))).scalar_one()
    open_orders = (await db.execute(select(func.count(MaintenanceOrder.id)).where(MaintenanceOrder.company_id == cid, MaintenanceOrder.status.notin_(["completed", "cancelled"])))).scalar_one()
    completed_orders = (await db.execute(select(func.count(MaintenanceOrder.id)).where(MaintenanceOrder.company_id == cid, MaintenanceOrder.status == "completed"))).scalar_one()
    total_assets = (await db.execute(select(func.count(MaintenanceAsset.id)).where(MaintenanceAsset.company_id == cid))).scalar_one()
    low_stock = (await db.execute(select(func.count(MaintenancePart.id)).where(MaintenancePart.company_id == cid, MaintenancePart.quantity_on_hand <= MaintenancePart.reorder_level))).scalar_one()
    open_incidents = (await db.execute(select(func.count(MaintenanceIncident.id)).where(MaintenanceIncident.company_id == cid, MaintenanceIncident.status.in_(["open", "investigating"])))).scalar_one()
    budget_planned = (await db.execute(select(func.coalesce(func.sum(MaintenanceBudget.planned_amount), 0)).where(MaintenanceBudget.company_id == cid))).scalar_one()
    utilization = (total / budget_planned * 100) if budget_planned and budget_planned > 0 else Decimal("0")
    utilization = utilization.quantize(Decimal("0.01"))
    return ResponseBase(data=MaintenanceAnalyticsSummary(
        total_cost=total, labor_cost=labor, parts_cost=parts, contractor_cost=contractor, other_cost=other,
        open_orders=open_orders, completed_orders=completed_orders, total_assets=total_assets,
        low_stock_parts=low_stock, open_incidents=open_incidents, budget_utilization=utilization,
    ))


# ── Phase 6: Configuration ────────────────────────────────────────────────────

@router.get("/config/work-types", response_model=ResponseBase[list[MaintenanceWorkTypeResponse]])
async def list_work_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceWorkType).where(MaintenanceWorkType.company_id == current_user.company_id).order_by(MaintenanceWorkType.name)
    )).scalars().all()
    return ResponseBase(data=[MaintenanceWorkTypeResponse.model_validate(w) for w in rows])


@router.post("/config/work-types", response_model=ResponseBase[MaintenanceWorkTypeResponse], status_code=201)
async def create_work_type(
    data: MaintenanceWorkTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dup = (await db.execute(select(MaintenanceWorkType.id).where(
        MaintenanceWorkType.company_id == current_user.company_id,
        MaintenanceWorkType.name == data.name.strip(),
    ))).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="ამ სახელით ტიპი უკვე არსებობს")
    w = MaintenanceWorkType(company_id=current_user.company_id, **data.model_dump())
    db.add(w)
    await db.flush()
    return ResponseBase(data=MaintenanceWorkTypeResponse.model_validate(w), message="ტიპი დაემატა")


@router.get("/config/priorities", response_model=ResponseBase[list[MaintenancePriorityResponse]])
async def list_priorities(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenancePriority).where(MaintenancePriority.company_id == current_user.company_id).order_by(MaintenancePriority.level)
    )).scalars().all()
    return ResponseBase(data=[MaintenancePriorityResponse.model_validate(p) for p in rows])


@router.post("/config/priorities", response_model=ResponseBase[MaintenancePriorityResponse], status_code=201)
async def create_priority(
    data: MaintenancePriorityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = MaintenancePriority(company_id=current_user.company_id, **data.model_dump())
    db.add(p)
    await db.flush()
    return ResponseBase(data=MaintenancePriorityResponse.model_validate(p), message="პრიორიტეტი დაემატა")


@router.get("/config/statuses", response_model=ResponseBase[list[MaintenanceStatusConfigResponse]])
async def list_status_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceStatusConfig).where(MaintenanceStatusConfig.company_id == current_user.company_id).order_by(MaintenanceStatusConfig.name)
    )).scalars().all()
    return ResponseBase(data=[MaintenanceStatusConfigResponse.model_validate(s) for s in rows])


@router.post("/config/statuses", response_model=ResponseBase[MaintenanceStatusConfigResponse], status_code=201)
async def create_status_config(
    data: MaintenanceStatusConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dup = (await db.execute(select(MaintenanceStatusConfig.id).where(
        MaintenanceStatusConfig.company_id == current_user.company_id,
        MaintenanceStatusConfig.code == data.code.strip(),
    ))).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="ამ კოდით სტატუსი უკვე არსებობს")
    s = MaintenanceStatusConfig(company_id=current_user.company_id, **data.model_dump())
    db.add(s)
    await db.flush()
    return ResponseBase(data=MaintenanceStatusConfigResponse.model_validate(s), message="სტატუსი დაემატა")


@router.get("/config/numbering", response_model=ResponseBase[list[MaintenanceNumberingConfigResponse]])
async def list_numbering_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(MaintenanceNumberingConfig).where(MaintenanceNumberingConfig.company_id == current_user.company_id).order_by(MaintenanceNumberingConfig.entity)
    )).scalars().all()
    return ResponseBase(data=[MaintenanceNumberingConfigResponse.model_validate(n) for n in rows])


@router.post("/config/numbering", response_model=ResponseBase[MaintenanceNumberingConfigResponse], status_code=201)
async def create_numbering_config(
    data: MaintenanceNumberingConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dup = (await db.execute(select(MaintenanceNumberingConfig.id).where(
        MaintenanceNumberingConfig.company_id == current_user.company_id,
        MaintenanceNumberingConfig.entity == data.entity.strip(),
    ))).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="ამ ერთეულისთვის ნომერაცია უკვე არსებობს")
    n = MaintenanceNumberingConfig(company_id=current_user.company_id, **data.model_dump())
    db.add(n)
    await db.flush()
    return ResponseBase(data=MaintenanceNumberingConfigResponse.model_validate(n), message="ნომერაცია დაემატა")

"""CRM pipeline forecast, bulk actions, duplicate detection, conversion tracking, lead source analytics, stale lead alerts."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.time import utc_now
from app.models.crm import CRMActivity, CRMLead, CRMOpportunity, CRMPipelineStage
from app.models.user import User
from app.schemas.common import ResponseBase, PaginatedResponse
from app.schemas.crm import (
    ConversionRateResponse,
    LeadSourceStats,
    LeadSourceTrackingResponse,
    PipelineStageValue,
    PipelineValueResponse,
    StaleLeadAlert,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/crm", tags=["CRM — გაძლიერებული"])


# ── Pipeline Forecast ──────────────────────────────────────────────────────────

class StageForecast(BaseModel):
    stage: str
    stage_label: str
    count: int
    total_amount: Decimal
    weighted_amount: Decimal  # amount * probability / 100
    avg_probability: float


class PipelineForecast(BaseModel):
    stages: list[StageForecast]
    total_pipeline: Decimal
    total_weighted: Decimal
    won_last_30d: Decimal
    lost_last_30d: Decimal
    conversion_rate: float  # won / (won + lost)


@router.get("/forecast", response_model=ResponseBase[PipelineForecast])
async def pipeline_forecast(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("crm", "can_access")),
):
    stage_rows = (await db.execute(
        select(CRMPipelineStage.key, CRMPipelineStage.name).where(
            CRMPipelineStage.company_id == current_user.company_id,
        )
    )).all()
    stage_labels = {key: name for key, name in stage_rows}

    # Per-stage aggregation — use Numeric(14,2) cast for sum to avoid type issues
    rows = (await db.execute(
        select(
            CRMOpportunity.stage,
            func.count(CRMOpportunity.id),
            func.coalesce(func.sum(CRMOpportunity.amount), 0).label("total"),
            func.avg(CRMOpportunity.probability),
        ).where(
            CRMOpportunity.company_id == current_user.company_id
        ).group_by(CRMOpportunity.stage)
    )).all()

    stages = []
    for stage, count, total, avg_prob in rows:
        # Ensure total is Decimal, not int
        if not isinstance(total, Decimal):
            total = Decimal(str(total))
        avg_p = float(avg_prob or 0)
        weighted = total * Decimal(str(avg_p)) / Decimal("100")
        stages.append(StageForecast(
            stage=stage, stage_label=stage_labels.get(stage, stage),
            count=count, total_amount=total, weighted_amount=weighted,
            avg_probability=avg_p,
        ))

    # Won/lost in last 30 days
    thirty_days_ago = utc_now() - timedelta(days=30)
    won = (await db.execute(
        select(func.coalesce(func.sum(CRMOpportunity.amount), 0)).where(
            CRMOpportunity.company_id == current_user.company_id,
            CRMOpportunity.stage == "won",
            CRMOpportunity.updated_at >= thirty_days_ago,
        )
    )).scalar()

    lost = (await db.execute(
        select(func.coalesce(func.sum(CRMOpportunity.amount), 0)).where(
            CRMOpportunity.company_id == current_user.company_id,
            CRMOpportunity.stage == "lost",
            CRMOpportunity.updated_at >= thirty_days_ago,
        )
    )).scalar()

    # Ensure Decimal
    if not isinstance(won, Decimal):
        won = Decimal(str(won or 0))
    if not isinstance(lost, Decimal):
        lost = Decimal(str(lost or 0))

    # Conversion rate
    won_count = (await db.execute(
        select(func.count(CRMOpportunity.id)).where(
            CRMOpportunity.company_id == current_user.company_id,
            CRMOpportunity.stage == "won",
        )
    )).scalar()
    lost_count = (await db.execute(
        select(func.count(CRMOpportunity.id)).where(
            CRMOpportunity.company_id == current_user.company_id,
            CRMOpportunity.stage == "lost",
        )
    )).scalar()
    total_decided = won_count + lost_count
    conversion_rate = won_count / total_decided if total_decided > 0 else 0.0

    total_pipeline = sum((s.total_amount for s in stages if s.stage not in ("won", "lost")), Decimal("0"))
    total_weighted = sum((s.weighted_amount for s in stages if s.stage not in ("won", "lost")), Decimal("0"))

    return ResponseBase(data=PipelineForecast(
        stages=stages, total_pipeline=total_pipeline, total_weighted=total_weighted,
        won_last_30d=won, lost_last_30d=lost, conversion_rate=conversion_rate,
    ))


# ── Pipeline Value by Stage (fixed) ──────────────────────────────────────────────

@router.get("/pipeline-value", response_model=ResponseBase[PipelineValueResponse])
async def pipeline_value_by_stage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("crm", "can_access")),
):
    """Return pipeline value aggregated by stage, excluding won/lost.
    Backfills: any qualified lead without an opportunity gets one auto-created,
    so the pipeline forecast is never empty for qualified leads."""
    # Backfill — qualified leads must have an opportunity
    qualified_leads = (await db.execute(
        select(CRMLead).where(
            CRMLead.company_id == current_user.company_id,
            CRMLead.status == "qualified",
            CRMLead.converted_client_id.is_(None),
        )
    )).scalars().all()
    for lead in qualified_leads:
        existing = (await db.execute(
            select(CRMOpportunity.id).where(
                CRMOpportunity.company_id == current_user.company_id,
                CRMOpportunity.lead_id == lead.id,
            )
        )).scalar_one_or_none()
        if not existing:
            db.add(CRMOpportunity(
                company_id=current_user.company_id,
                lead_id=lead.id,
                name=lead.company_name or lead.contact_name or lead.email or "უსახელო შესაძლებლობა",
                stage="qualification",
                amount=lead.estimated_value if lead.estimated_value is not None else 0,
                expected_close_date=lead.next_action_date,
                owner_id=lead.owner_id,
                team_id=lead.team_id,
            ))
    if qualified_leads:
        await db.flush()

    stage_rows = (await db.execute(
        select(CRMPipelineStage.key, CRMPipelineStage.name).where(
            CRMPipelineStage.company_id == current_user.company_id,
        )
    )).all()
    stage_labels = {key: name for key, name in stage_rows}

    rows = (await db.execute(
        select(
            CRMOpportunity.stage,
            func.count(CRMOpportunity.id),
            func.coalesce(func.sum(CRMOpportunity.amount), 0),
            func.avg(CRMOpportunity.probability),
        ).where(
            CRMOpportunity.company_id == current_user.company_id,
            CRMOpportunity.stage.notin_(["won", "lost"]),
        ).group_by(CRMOpportunity.stage)
    )).all()

    stages = []
    for stage, count, total, avg_prob in rows:
        if not isinstance(total, Decimal):
            total = Decimal(str(total or 0))
        avg_p = float(avg_prob or 0)
        weighted = total * Decimal(str(avg_p)) / Decimal("100")
        stages.append(PipelineStageValue(
            stage=stage, stage_label=stage_labels.get(stage, stage),
            count=count, total_amount=total, weighted_amount=weighted,
        ))

    total_pipeline = sum((s.total_amount for s in stages), Decimal("0"))
    total_weighted = sum((s.weighted_amount for s in stages), Decimal("0"))

    return ResponseBase(data=PipelineValueResponse(
        stages=stages,
        total_pipeline_value=total_pipeline,
        total_weighted_value=total_weighted,
    ))


# ── Conversion Rate Tracking (leads → clients) ──────────────────────────────────

@router.get("/conversion-rate", response_model=ResponseBase[ConversionRateResponse])
async def conversion_rate(
    days: int = Query(90, ge=1, le=365, description="პერიოდი დღეებში"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("crm", "can_access")),
):
    """Return lead-to-client conversion rate for the given period."""
    company_id = current_user.company_id
    cutoff = utc_now() - timedelta(days=days)

    total_leads = (await db.execute(
        select(func.count(CRMLead.id)).where(
            CRMLead.company_id == company_id,
            CRMLead.created_at >= cutoff,
        )
    )).scalar()

    converted_leads = (await db.execute(
        select(func.count(CRMLead.id)).where(
            CRMLead.company_id == company_id,
            CRMLead.status == "converted",
            CRMLead.converted_at >= cutoff,
        )
    )).scalar()

    rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0.0

    return ResponseBase(data=ConversionRateResponse(
        total_leads=total_leads,
        converted_leads=converted_leads,
        conversion_rate=round(rate, 2),
        period_days=days,
    ))


# ── Lead Source Tracking ──────────────────────────────────────────────────────────

@router.get("/lead-sources", response_model=ResponseBase[LeadSourceTrackingResponse])
async def lead_source_tracking(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("crm", "can_access")),
):
    """Return lead statistics grouped by source."""
    company_id = current_user.company_id

    rows = (await db.execute(
        select(
            CRMLead.source,
            func.count(CRMLead.id),
            func.coalesce(func.sum(CRMLead.estimated_value), 0),
        ).where(
            CRMLead.company_id == company_id,
        ).group_by(CRMLead.source)
    )).all()

    sources = []
    total_leads = 0
    total_converted = 0

    for source, count, total_value in rows:
        if not isinstance(total_value, Decimal):
            total_value = Decimal(str(total_value or 0))

        converted_count = (await db.execute(
            select(func.count(CRMLead.id)).where(
                CRMLead.company_id == company_id,
                CRMLead.source == source,
                CRMLead.status == "converted",
            )
        )).scalar()

        conv_rate = (converted_count / count * 100) if count > 0 else 0.0

        sources.append(LeadSourceStats(
            source=source,
            count=count,
            total_value=total_value,
            converted_count=converted_count,
            conversion_rate=round(conv_rate, 2),
        ))
        total_leads += count
        total_converted += converted_count

    return ResponseBase(data=LeadSourceTrackingResponse(
        sources=sources,
        total_leads=total_leads,
        total_converted=total_converted,
    ))


# ── Stale Lead Alerts ────────────────────────────────────────────────────────────

class StaleLeadAlertResponse(BaseModel):
    id: UUID
    company_name: str
    contact_name: str | None = None
    status: str
    source: str | None = None
    estimated_value: Decimal | None = None
    days_since_last_activity: int
    last_activity_at: datetime | None = None
    next_action_date: date | None = None
    owner_id: UUID | None = None
    created_at: datetime


@router.get("/stale-leads", response_model=ResponseBase[list[StaleLeadAlertResponse]])
async def stale_leads(
    threshold_days: int = Query(30, ge=1, le=365, description="უმოქმედობის ზღვარი დღეებში"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("crm", "can_access")),
):
    """Return leads with no activity in the last N days (stale follow-up). Default 30 days."""
    company_id = current_user.company_id
    now = utc_now()

    # Get all non-converted, non-unqualified leads
    leads = (await db.execute(
        select(CRMLead).where(
            CRMLead.company_id == company_id,
            CRMLead.status.notin_(["converted", "unqualified"]),
        )
    )).scalars().all()

    result = []
    for lead in leads:
        # Get latest activity for this lead
        last_activity = (await db.execute(
            select(CRMActivity.created_at)
            .where(
                CRMActivity.company_id == company_id,
                CRMActivity.lead_id == lead.id,
            )
            .order_by(CRMActivity.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        # Also check opportunity updates
        last_opp_update = (await db.execute(
            select(CRMOpportunity.updated_at)
            .where(
                CRMOpportunity.company_id == company_id,
                CRMOpportunity.lead_id == lead.id,
            )
            .order_by(CRMOpportunity.updated_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        # Use the most recent of: activity, opp update, lead's last_activity_at, lead created_at
        last_date = (
            last_activity
            or last_opp_update
            or lead.last_activity_at
            or lead.created_at
        )
        days_since = (now - last_date).days if last_date else 0

        if days_since >= threshold_days:
            result.append(StaleLeadAlertResponse(
                id=lead.id, company_name=lead.company_name,
                contact_name=lead.contact_name, status=lead.status,
                source=lead.source, estimated_value=lead.estimated_value,
                days_since_last_activity=days_since,
                last_activity_at=last_date if isinstance(last_date, datetime) else None,
                next_action_date=lead.next_action_date,
                owner_id=lead.owner_id,
                created_at=lead.created_at,
            ))

    return ResponseBase(data=sorted(result, key=lambda x: x.days_since_last_activity, reverse=True))


# ── Bulk Actions ────────────────────────────────────────────────────────────────

class BulkStatusUpdate(BaseModel):
    ids: list[UUID]
    status: str = Field(..., max_length=30)


class BulkDeleteRequest(BaseModel):
    ids: list[UUID]


@router.post("/leads/bulk/status", response_model=ResponseBase[dict])
async def bulk_update_lead_status(
    data: BulkStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("crm", "can_edit")),
):
    result = await db.execute(
        update(CRMLead)
        .where(
            CRMLead.id.in_(data.ids),
            CRMLead.company_id == current_user.company_id,
            CRMLead.status != "converted",
        )
        .values(status=data.status)
    )
    await db.flush()
    return ResponseBase(data={"updated": result.rowcount, "status": data.status})


@router.post("/opportunities/bulk/stage", response_model=ResponseBase[dict])
async def bulk_update_opportunity_stage(
    data: BulkStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("crm", "can_edit")),
):
    result = await db.execute(
        update(CRMOpportunity)
        .where(
            CRMOpportunity.id.in_(data.ids),
            CRMOpportunity.company_id == current_user.company_id,
        )
        .values(stage=data.status)
    )
    await db.flush()
    return ResponseBase(data={"updated": result.rowcount, "stage": data.status})


# ── Duplicate Detection ──────────────────────────────────────────────────────────

class DuplicateCheckRequest(BaseModel):
    company_name: str = Field(..., max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None


class DuplicateCheckResponse(BaseModel):
    has_duplicates: bool
    leads: list[dict]
    opportunities: list[dict]
    clients: list[dict]


@router.post("/leads/check-duplicates", response_model=ResponseBase[DuplicateCheckResponse])
async def check_duplicates(
    data: DuplicateCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("crm", "can_access")),
):
    company_id = current_user.company_id
    term = f"%{data.company_name.strip()}%"

    # Check leads
    lead_rows = (await db.execute(
        select(CRMLead.id, CRMLead.company_name, CRMLead.status, CRMLead.created_at).where(
            CRMLead.company_id == company_id,
            CRMLead.status != "converted",
            or_(
                CRMLead.company_name.ilike(term),
                CRMLead.email.ilike(term) if data.email else False,
                CRMLead.phone == data.phone if data.phone else False,
            ),
        ).limit(5)
    )).all()

    # Check opportunities
    opp_rows = (await db.execute(
        select(CRMOpportunity.id, CRMOpportunity.name, CRMOpportunity.stage, CRMOpportunity.amount).where(
            CRMOpportunity.company_id == company_id,
            CRMOpportunity.stage.notin_(["won", "lost"]),
            CRMOpportunity.name.ilike(term),
        ).limit(5)
    )).all()

    # Check clients
    from app.models.client import Client
    client_rows = (await db.execute(
        select(Client.id, Client.name, Client.identification_code).where(
            Client.company_id == company_id,
            Client.deleted_at.is_(None),
            Client.name.ilike(term),
        ).limit(5)
    )).all()

    leads = [{"id": str(r[0]), "name": r[1], "status": r[2], "created_at": str(r[3])} for r in lead_rows]
    opportunities = [{"id": str(r[0]), "name": r[1], "stage": r[2], "amount": float(r[3])} for r in opp_rows]
    clients = [{"id": str(r[0]), "name": r[1], "identification_code": r[2]} for r in client_rows]

    return ResponseBase(data=DuplicateCheckResponse(
        has_duplicates=bool(leads or opportunities or clients),
        leads=leads, opportunities=opportunities, clients=clients,
    ))

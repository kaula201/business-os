from uuid import UUID

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.client import Client, ClientStatus, Contact
from app.models.crm import (
    CRMActivity, CRMCampaignAttribution, CRMContact, CRMEmailMessage, CRMEmailThread,
    CRMGdprConsent, CRMLead, CRMOpportunity, CRMPipelineStage, CRMRoutingRule,
    CRMSLA, CRMTelephonyCall, CRMTerritory,
)
from app.models.sales_team import SalesTeam
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.client import ClientResponse, ContactResponse
from app.schemas.crm import (
    CRMActivityCreate,
    CRMActivityResponse,
    CRMActivityUpdate,
    CRMLeadCreate,
    CRMLeadConvertRequest,
    CRMLeadConvertResponse,
    CRMLeadResponse,
    CRMLeadUpdate,
    CRMOpportunityCreate,
    CRMOpportunityResponse,
    CRMOpportunityUpdate,
    CRMPipelineReorderRequest,
    CRMPipelineStageCreate,
    CRMPipelineStageResponse,
    CRMPipelineStageUpdate,
    LeadScoreBreakdown,
    LeadScoreResponse,
)

router = APIRouter(prefix="/crm", tags=["CRM — ლიდები და გაყიდვები"])

# Default pipeline stages seeded for every company (Odoo-style kanban columns).
DEFAULT_STAGES = [
    {"key": "qualification", "name": "კვალიფიკაცია", "probability": 10, "color": "#3b82f6", "sort_order": 0},
    {"key": "discovery", "name": "საჭიროებების კვლევა", "probability": 25, "color": "#8b5cf6", "sort_order": 1},
    {"key": "proposal", "name": "შეთავაზება", "probability": 50, "color": "#f59e0b", "sort_order": 2},
    {"key": "negotiation", "name": "მოლაპარაკება", "probability": 75, "color": "#ef4444", "sort_order": 3},
    {"key": "won", "name": "მოგებული", "probability": 100, "color": "#22c55e", "sort_order": 4, "is_won": True},
    {"key": "lost", "name": "დაკარგული", "probability": 0, "color": "#94a3b8", "sort_order": 5, "is_lost": True},
]


async def _ensure_stages_seeded(db: AsyncSession, company_id: UUID) -> None:
    """Seed default pipeline stages for a company on first access."""
    existing = (await db.execute(
        select(CRMPipelineStage.id).where(CRMPipelineStage.company_id == company_id).limit(1)
    )).scalar_one_or_none()
    if existing:
        return
    for s in DEFAULT_STAGES:
        db.add(CRMPipelineStage(company_id=company_id, **s))
    await db.flush()


async def _stage_keys(db: AsyncSession, company_id: UUID) -> set[str]:
    """Active stage keys for the company (seeded on demand)."""
    await _ensure_stages_seeded(db, company_id)
    rows = (await db.execute(
        select(CRMPipelineStage.key).where(
            CRMPipelineStage.company_id == company_id,
            CRMPipelineStage.is_active.is_(True),
        )
    )).scalars().all()
    return set(rows)


async def _validate_team(db: AsyncSession, company_id: UUID, team_id: UUID | None) -> None:
    if team_id is None:
        return
    team = (await db.execute(select(SalesTeam.id).where(
        SalesTeam.id == team_id,
        SalesTeam.company_id == company_id,
    ))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="გაყიდვების გუნდი არ მოიძებნა")


def _compute_lead_score(lead: CRMLead) -> int:
    """Deterministic lead scoring: source + contact info + value + activity."""
    score = 0
    source_points = {"website": 5, "referral": 10, "campaign": 5, "phone": 8, "email": 8, "other": 2}
    score += source_points.get(lead.source, 2)
    if lead.email:
        score += 10
    if lead.phone:
        score += 10
    if lead.contact_name:
        score += 5
    if lead.estimated_value and lead.estimated_value >= 10000:
        score += 20
    elif lead.estimated_value and lead.estimated_value >= 1000:
        score += 10
    if lead.next_action_date:
        score += 5
    if lead.last_activity_at:
        days_since = (utc_now() - lead.last_activity_at).days
        if days_since <= 7:
            score += 15
        elif days_since <= 30:
            score += 8
    return min(score, 100)


def _score_breakdown(lead: CRMLead) -> LeadScoreBreakdown:
    source_points = {"website": 5, "referral": 10, "campaign": 5, "phone": 8, "email": 8, "other": 2}
    source = source_points.get(lead.source, 2)
    contact = (10 if lead.email else 0) + (10 if lead.phone else 0) + (5 if lead.contact_name else 0)
    value = 20 if (lead.estimated_value and lead.estimated_value >= 10000) else (10 if (lead.estimated_value and lead.estimated_value >= 1000) else 0)
    activity = 0
    if lead.next_action_date:
        activity += 5
    if lead.last_activity_at:
        days_since = (utc_now() - lead.last_activity_at).days
        if days_since <= 7:
            activity += 15
        elif days_since <= 30:
            activity += 8
    return LeadScoreBreakdown(
        source=source, contact_info=contact, value=value, activity=activity,
        total=min(source + contact + value + activity, 100),
    )


def opportunity_response(opportunity: CRMOpportunity, lead_company_name: str | None = None) -> CRMOpportunityResponse:
    return CRMOpportunityResponse.model_validate(opportunity).model_copy(
        update={"lead_company_name": lead_company_name}
    )


def activity_response(activity: CRMActivity, related_name: str | None = None) -> CRMActivityResponse:
    return CRMActivityResponse.model_validate(activity).model_copy(update={"related_name": related_name})


@router.post("/leads", response_model=ResponseBase[CRMLeadResponse], status_code=status.HTTP_201_CREATED)
async def create_lead(
    data: CRMLeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _validate_team(db, current_user.company_id, data.team_id)
    lead = CRMLead(
        company_id=current_user.company_id,
        owner_id=data.owner_id or current_user.id,
        team_id=data.team_id,
        company_name=data.company_name.strip(),
        contact_name=data.contact_name.strip() if data.contact_name else None,
        email=str(data.email) if data.email else None,
        phone=data.phone.strip() if data.phone else None,
        source=data.source,
        estimated_value=data.estimated_value,
        notes=data.notes,
        next_action_date=data.next_action_date,
        last_activity_at=utc_now(),
    )
    lead.score = _compute_lead_score(lead)
    db.add(lead)
    await db.flush()
    add_audit(db, current_user, "crm.lead_created", "crm_lead", lead.id, {
        "company_name": lead.company_name,
        "source": lead.source,
        "estimated_value": lead.estimated_value,
        "score": lead.score,
    })
    await db.flush()
    return ResponseBase(data=CRMLeadResponse.model_validate(lead))


@router.get("/leads", response_model=ResponseBase[PaginatedResponse[CRMLeadResponse]])
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    lead_status: str | None = Query(None, alias="status"),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [CRMLead.company_id == current_user.company_id]
    if lead_status:
        filters.append(CRMLead.status == lead_status)
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(CRMLead.company_name.ilike(term), CRMLead.contact_name.ilike(term), CRMLead.email.ilike(term)))
    total = (await db.execute(select(func.count(CRMLead.id)).where(*filters))).scalar_one()
    leads = (
        await db.execute(
            select(CRMLead)
            .where(*filters)
            .order_by(CRMLead.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[CRMLeadResponse.model_validate(lead) for lead in leads],
    ))


@router.patch("/leads/{lead_id}", response_model=ResponseBase[CRMLeadResponse])
async def update_lead(
    lead_id: UUID,
    data: CRMLeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = (
        await db.execute(
            select(CRMLead)
            .where(CRMLead.id == lead_id, CRMLead.company_id == current_user.company_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="ლიდი არ მოიძებნა")
    if lead.status == "converted":
        raise HTTPException(status_code=409, detail="გადაყვანილი ლიდის შეცვლა აღარ შეიძლება")
    if data.owner_id:
        owner = (await db.execute(select(User.id).where(
            User.id == data.owner_id,
            User.company_id == current_user.company_id,
        ))).scalar_one_or_none()
        if not owner:
            raise HTTPException(status_code=404, detail="პასუხისმგებელი თანამშრომელი არ მოიძებნა")
    if data.team_id is not None:
        await _validate_team(db, current_user.company_id, data.team_id)
    before_status = lead.status
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "email" and value is not None:
            value = str(value)
        setattr(lead, field, value)
    # Track last activity on any update
    lead.last_activity_at = utc_now()
    lead.score = _compute_lead_score(lead)
    # Auto-create a pipeline opportunity the moment a lead is qualified,
    # so the pipeline forecast is never empty for qualified leads.
    if before_status != "qualified" and lead.status == "qualified":
        existing_opp = (
            await db.execute(
                select(CRMOpportunity.id).where(
                    CRMOpportunity.company_id == current_user.company_id,
                    CRMOpportunity.lead_id == lead.id,
                )
            )
        ).scalar_one_or_none()
        if not existing_opp:
            estimated_value = data.estimated_value if data.estimated_value is not None else lead.estimated_value
            db.add(CRMOpportunity(
                company_id=current_user.company_id,
                lead_id=lead.id,
                name=lead.company_name or lead.contact_name or lead.email or "უსახელო შესაძლებლობა",
                stage="qualification",
                amount=estimated_value if estimated_value is not None else 0,
                expected_close_date=lead.next_action_date,
                owner_id=data.owner_id or lead.owner_id,
                team_id=data.team_id if data.team_id is not None else lead.team_id,
            ))
            add_audit(db, current_user, "crm.opportunity_auto_created", "crm_opportunity", lead.id, {
                "lead_id": str(lead.id),
                "stage": "qualification",
            })
    add_audit(db, current_user, "crm.lead_updated", "crm_lead", lead.id, {
        "before_status": before_status,
        "after_status": lead.status,
    })
    await db.flush()
    await db.refresh(lead)
    return ResponseBase(data=CRMLeadResponse.model_validate(lead))


@router.post(
    "/leads/{lead_id}/convert",
    response_model=ResponseBase[CRMLeadConvertResponse],
    status_code=status.HTTP_201_CREATED,
)
async def convert_lead(
    lead_id: UUID,
    data: CRMLeadConvertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = (
        await db.execute(
            select(CRMLead)
            .where(CRMLead.id == lead_id, CRMLead.company_id == current_user.company_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="ლიდი არ მოიძებნა")
    if lead.status == "converted" or lead.converted_client_id:
        raise HTTPException(status_code=409, detail="ლიდი უკვე გადაყვანილია კლიენტების რეესტრში")
    if lead.status != "qualified":
        raise HTTPException(status_code=409, detail="კლიენტად გადაყვანამდე ლიდი კვალიფიცირებული უნდა იყოს")

    identification_code = data.identification_code.strip()
    duplicate = (await db.execute(select(Client.id).where(
        Client.company_id == current_user.company_id,
        Client.identification_code == identification_code,
        Client.deleted_at.is_(None),
    ))).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="ამ საიდენტიფიკაციო კოდით კლიენტი უკვე არსებობს")

    client = Client(
        company_id=current_user.company_id,
        client_type=data.client_type,
        name=(data.name or lead.company_name).strip(),
        identification_code=identification_code,
        vat_status=data.is_vat_payer,
        address=data.address,
        status=ClientStatus.POTENTIAL,
        notes=data.notes or lead.notes,
        created_by=current_user.id,
    )
    db.add(client)
    await db.flush()

    contact = Contact(
        client_id=client.id,
        full_name=(lead.contact_name or lead.company_name).strip(),
        phone=lead.phone,
        email=lead.email,
        is_primary=True,
    )
    db.add(contact)
    await db.flush()

    lead.status = "converted"
    lead.converted_client_id = client.id
    lead.converted_at = utc_now()
    await db.execute(
        update(CRMOpportunity)
        .where(CRMOpportunity.company_id == current_user.company_id, CRMOpportunity.lead_id == lead.id)
        .values(client_id=client.id)
    )
    add_audit(db, current_user, "crm.lead_converted", "crm_lead", lead.id, {
        "client_id": client.id,
        "identification_code": client.identification_code,
    })
    add_audit(db, current_user, "crm.client_created_from_lead", "client", client.id, {
        "lead_id": lead.id,
    })
    await db.flush()
    await db.refresh(lead)
    await db.refresh(client)

    client_response = ClientResponse(
        id=client.id,
        company_id=client.company_id,
        client_type=client.client_type,
        name=client.name,
        identification_code=client.identification_code,
        is_vat_payer=client.vat_status,
        address=client.address,
        phone=contact.phone,
        email=contact.email,
        status=client.status,
        notes=client.notes,
        contacts=[ContactResponse.model_validate(contact)],
        created_at=client.created_at,
        updated_at=client.updated_at,
    )
    return ResponseBase(data=CRMLeadConvertResponse(
        lead=CRMLeadResponse.model_validate(lead),
        client=client_response,
    ))


@router.post("/opportunities", response_model=ResponseBase[CRMOpportunityResponse], status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    data: CRMOpportunityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = None
    if data.lead_id:
        lead = (
            await db.execute(
                select(CRMLead).where(CRMLead.id == data.lead_id, CRMLead.company_id == current_user.company_id)
            )
        ).scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="ლიდი არ მოიძებნა")
    if data.client_id:
        client = (
            await db.execute(
                select(Client).where(Client.id == data.client_id, Client.company_id == current_user.company_id, Client.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")
    stage_keys = await _stage_keys(db, current_user.company_id)
    if data.stage not in stage_keys:
        raise HTTPException(status_code=400, detail="მითითებული pipeline ეტაპი არ არსებობს")
    await _validate_team(db, current_user.company_id, data.team_id)
    opportunity = CRMOpportunity(
        company_id=current_user.company_id,
        lead_id=data.lead_id,
        client_id=data.client_id,
        owner_id=data.owner_id or current_user.id,
        team_id=data.team_id,
        name=data.name.strip(),
        stage=data.stage,
        amount=data.amount,
        probability=data.probability,
        expected_close_date=data.expected_close_date,
        notes=data.notes,
    )
    db.add(opportunity)
    await db.flush()
    add_audit(db, current_user, "crm.opportunity_created", "crm_opportunity", opportunity.id, {
        "name": opportunity.name,
        "stage": opportunity.stage,
        "amount": opportunity.amount,
        "lead_id": opportunity.lead_id,
    })
    await db.flush()
    return ResponseBase(data=opportunity_response(opportunity, lead.company_name if lead else None))


@router.get("/opportunities", response_model=ResponseBase[PaginatedResponse[CRMOpportunityResponse]])
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    stage: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [CRMOpportunity.company_id == current_user.company_id]
    if stage:
        filters.append(CRMOpportunity.stage == stage)
    total = (await db.execute(select(func.count(CRMOpportunity.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(CRMOpportunity, CRMLead.company_name)
            .outerjoin(CRMLead, CRMLead.id == CRMOpportunity.lead_id)
            .where(*filters)
            .order_by(CRMOpportunity.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return ResponseBase(data=PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[opportunity_response(opportunity, company_name) for opportunity, company_name in rows],
    ))


@router.patch("/opportunities/{opportunity_id}", response_model=ResponseBase[CRMOpportunityResponse])
async def update_opportunity(
    opportunity_id: UUID,
    data: CRMOpportunityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = (
        await db.execute(
            select(CRMOpportunity)
            .where(CRMOpportunity.id == opportunity_id, CRMOpportunity.company_id == current_user.company_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not opportunity:
        raise HTTPException(status_code=404, detail="გაყიდვების შესაძლებლობა არ მოიძებნა")
    if data.stage is not None:
        stage_keys = await _stage_keys(db, current_user.company_id)
        if data.stage not in stage_keys:
            raise HTTPException(status_code=400, detail="მითითებული pipeline ეტაპი არ არსებობს")
    if data.team_id is not None:
        await _validate_team(db, current_user.company_id, data.team_id)
    before_stage = opportunity.stage
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(opportunity, field, value)
    # Auto probability from the configured stage when the stage changes.
    if data.stage is not None and data.stage != before_stage and "probability" not in data.model_fields_set:
        stage_row = (await db.execute(
            select(CRMPipelineStage).where(
                CRMPipelineStage.company_id == current_user.company_id,
                CRMPipelineStage.key == opportunity.stage,
            )
        )).scalar_one_or_none()
        if stage_row:
            opportunity.probability = stage_row.probability
    add_audit(db, current_user, "crm.opportunity_updated", "crm_opportunity", opportunity.id, {
        "before_stage": before_stage,
        "after_stage": opportunity.stage,
        "amount": opportunity.amount,
        "probability": opportunity.probability,
    })
    await db.flush()
    await db.refresh(opportunity)
    lead_name = None
    if opportunity.lead_id:
        lead_name = (
            await db.execute(select(CRMLead.company_name).where(CRMLead.id == opportunity.lead_id))
        ).scalar_one_or_none()
    return ResponseBase(data=opportunity_response(opportunity, lead_name))


@router.post("/activities", response_model=ResponseBase[CRMActivityResponse], status_code=status.HTTP_201_CREATED)
async def create_activity(
    data: CRMActivityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    related_name = None
    if data.lead_id:
        related_name = (
            await db.execute(select(CRMLead.company_name).where(
                CRMLead.id == data.lead_id,
                CRMLead.company_id == current_user.company_id,
            ))
        ).scalar_one_or_none()
    elif data.opportunity_id:
        related_name = (
            await db.execute(select(CRMOpportunity.name).where(
                CRMOpportunity.id == data.opportunity_id,
                CRMOpportunity.company_id == current_user.company_id,
            ))
        ).scalar_one_or_none()
    elif data.client_id:
        related_name = (
            await db.execute(select(Client.name).where(
                Client.id == data.client_id,
                Client.company_id == current_user.company_id,
                Client.deleted_at.is_(None),
            ))
        ).scalar_one_or_none()
    if related_name is None:
        raise HTTPException(status_code=404, detail="აქტივობასთან დაკავშირებული ჩანაწერი არ მოიძებნა")

    activity = CRMActivity(
        company_id=current_user.company_id,
        lead_id=data.lead_id,
        opportunity_id=data.opportunity_id,
        client_id=data.client_id,
        assigned_to=data.assigned_to or current_user.id,
        created_by=current_user.id,
        activity_type=data.activity_type,
        subject=data.subject.strip(),
        description=data.description,
        due_at=data.due_at,
    )
    db.add(activity)
    await db.flush()
    add_audit(db, current_user, "crm.activity_created", "crm_activity", activity.id, {
        "activity_type": activity.activity_type,
        "subject": activity.subject,
        "due_at": activity.due_at,
    })
    await db.flush()
    return ResponseBase(data=activity_response(activity, related_name))


@router.get("/activities", response_model=ResponseBase[PaginatedResponse[CRMActivityResponse]])
async def list_activities(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    activity_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [CRMActivity.company_id == current_user.company_id]
    if activity_status:
        filters.append(CRMActivity.status == activity_status)
    total = (await db.execute(select(func.count(CRMActivity.id)).where(*filters))).scalar_one()
    activities = (
        await db.execute(
            select(CRMActivity)
            .where(*filters)
            .order_by(CRMActivity.due_at.asc().nulls_last(), CRMActivity.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    lead_ids = {item.lead_id for item in activities if item.lead_id}
    opportunity_ids = {item.opportunity_id for item in activities if item.opportunity_id}
    client_ids = {item.client_id for item in activities if item.client_id}
    lead_names = dict((await db.execute(
        select(CRMLead.id, CRMLead.company_name).where(
            CRMLead.company_id == current_user.company_id,
            CRMLead.id.in_(lead_ids),
        )
    )).all()) if lead_ids else {}
    opportunity_names = dict((await db.execute(
        select(CRMOpportunity.id, CRMOpportunity.name).where(
            CRMOpportunity.company_id == current_user.company_id,
            CRMOpportunity.id.in_(opportunity_ids),
        )
    )).all()) if opportunity_ids else {}
    client_names = dict((await db.execute(
        select(Client.id, Client.name).where(
            Client.company_id == current_user.company_id,
            Client.id.in_(client_ids),
            Client.deleted_at.is_(None),
        )
    )).all()) if client_ids else {}

    items = []
    for activity in activities:
        related_name = (
            lead_names.get(activity.lead_id)
            or opportunity_names.get(activity.opportunity_id)
            or client_names.get(activity.client_id)
        )
        items.append(activity_response(activity, related_name))
    return ResponseBase(data=PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    ))


@router.patch("/activities/{activity_id}", response_model=ResponseBase[CRMActivityResponse])
async def update_activity(
    activity_id: UUID,
    data: CRMActivityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    activity = (
        await db.execute(
            select(CRMActivity)
            .where(CRMActivity.id == activity_id, CRMActivity.company_id == current_user.company_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="აქტივობა არ მოიძებნა")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(activity, field, value)
    if data.status == "completed" and activity.completed_at is None:
        activity.completed_at = utc_now()
    elif data.status in {"planned", "cancelled"}:
        activity.completed_at = None

    add_audit(db, current_user, "crm.activity_updated", "crm_activity", activity.id, {
        "status": activity.status,
        "subject": activity.subject,
    })
    await db.flush()
    await db.refresh(activity)

    related_name = None
    if activity.lead_id:
        related_name = (await db.execute(select(CRMLead.company_name).where(
            CRMLead.id == activity.lead_id,
            CRMLead.company_id == current_user.company_id,
        ))).scalar_one_or_none()
    elif activity.opportunity_id:
        related_name = (await db.execute(select(CRMOpportunity.name).where(
            CRMOpportunity.id == activity.opportunity_id,
            CRMOpportunity.company_id == current_user.company_id,
        ))).scalar_one_or_none()
    elif activity.client_id:
        related_name = (await db.execute(select(Client.name).where(
            Client.id == activity.client_id,
            Client.company_id == current_user.company_id,
        ))).scalar_one_or_none()
    return ResponseBase(data=activity_response(activity, related_name))


# ── Configurable pipeline stages (kanban) ───────────────────────────────────

@router.get("/pipeline-stages", response_model=ResponseBase[list[CRMPipelineStageResponse]])
async def list_pipeline_stages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _ensure_stages_seeded(db, current_user.company_id)
    stages = (await db.execute(
        select(CRMPipelineStage)
        .where(CRMPipelineStage.company_id == current_user.company_id)
        .order_by(CRMPipelineStage.sort_order.asc(), CRMPipelineStage.created_at.asc())
    )).scalars().all()
    return ResponseBase(data=[CRMPipelineStageResponse.model_validate(s) for s in stages])


@router.post("/pipeline-stages", response_model=ResponseBase[CRMPipelineStageResponse], status_code=status.HTTP_201_CREATED)
async def create_pipeline_stage(
    data: CRMPipelineStageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _ensure_stages_seeded(db, current_user.company_id)
    duplicate = (await db.execute(select(CRMPipelineStage.id).where(
        CRMPipelineStage.company_id == current_user.company_id,
        CRMPipelineStage.key == data.key,
    ))).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="ამ key-ით pipeline ეტაპი უკვე არსებობს")
    stage = CRMPipelineStage(company_id=current_user.company_id, **data.model_dump())
    db.add(stage)
    await db.flush()
    add_audit(db, current_user, "crm.stage_created", "crm_pipeline_stage", stage.id, {
        "key": stage.key, "name": stage.name, "sort_order": stage.sort_order,
    })
    await db.flush()
    return ResponseBase(data=CRMPipelineStageResponse.model_validate(stage))


@router.patch("/pipeline-stages/{stage_id}", response_model=ResponseBase[CRMPipelineStageResponse])
async def update_pipeline_stage(
    stage_id: UUID,
    data: CRMPipelineStageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stage = (await db.execute(
        select(CRMPipelineStage).where(
            CRMPipelineStage.id == stage_id,
            CRMPipelineStage.company_id == current_user.company_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if not stage:
        raise HTTPException(status_code=404, detail="Pipeline ეტაპი არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(stage, field, value)
    add_audit(db, current_user, "crm.stage_updated", "crm_pipeline_stage", stage.id, {
        "name": stage.name, "probability": stage.probability, "is_active": stage.is_active,
    })
    await db.flush()
    await db.refresh(stage)
    return ResponseBase(data=CRMPipelineStageResponse.model_validate(stage))


@router.delete("/pipeline-stages/{stage_id}", response_model=ResponseBase)
async def delete_pipeline_stage(
    stage_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stage = (await db.execute(
        select(CRMPipelineStage).where(
            CRMPipelineStage.id == stage_id,
            CRMPipelineStage.company_id == current_user.company_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if not stage:
        raise HTTPException(status_code=404, detail="Pipeline ეტაპი არ მოიძებნა")
    if stage.is_won or stage.is_lost:
        raise HTTPException(status_code=400, detail="მოგებული/დაკარგული ეტაპის წაშლა არ შეიძლება")
    used = (await db.execute(select(func.count(CRMOpportunity.id)).where(
        CRMOpportunity.company_id == current_user.company_id,
        CRMOpportunity.stage == stage.key,
    ))).scalar_one()
    if used:
        raise HTTPException(status_code=400, detail="ამ ეტაპზე შესაძლებლობებია — ჯერ გადაიტანეთ ისინი სხვა ეტაპზე")
    await db.delete(stage)
    add_audit(db, current_user, "crm.stage_deleted", "crm_pipeline_stage", stage.id, {"key": stage.key})
    await db.commit()
    return ResponseBase(message="Pipeline ეტაპი წაშლილია")


@router.post("/pipeline-stages/reorder", response_model=ResponseBase[list[CRMPipelineStageResponse]])
async def reorder_pipeline_stages(
    data: CRMPipelineReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ids = [item.id for item in data.stages]
    stages = (await db.execute(
        select(CRMPipelineStage).where(
            CRMPipelineStage.company_id == current_user.company_id,
            CRMPipelineStage.id.in_(ids),
        )
    )).scalars().all()
    by_id = {s.id: s for s in stages}
    for item in data.stages:
        if item.id in by_id:
            by_id[item.id].sort_order = item.sort_order
    await db.flush()
    ordered = (await db.execute(
        select(CRMPipelineStage)
        .where(CRMPipelineStage.company_id == current_user.company_id)
        .order_by(CRMPipelineStage.sort_order.asc(), CRMPipelineStage.created_at.asc())
    )).scalars().all()
    return ResponseBase(data=[CRMPipelineStageResponse.model_validate(s) for s in ordered])


# ── Lead scoring ─────────────────────────────────────────────────────────────

@router.get("/leads/{lead_id}/score", response_model=ResponseBase[LeadScoreResponse])
async def get_lead_score(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = (await db.execute(
        select(CRMLead).where(CRMLead.id == lead_id, CRMLead.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="ლიდი არ მოიძებნა")
    breakdown = _score_breakdown(lead)
    return ResponseBase(data=LeadScoreResponse(lead_id=lead.id, score=breakdown.total, breakdown=breakdown))


# ── CRM → Quotation + email ──────────────────────────────────────────────────

@router.post("/opportunities/{opportunity_id}/quotation", response_model=ResponseBase[dict], status_code=status.HTTP_201_CREATED)
async def create_quotation_from_opportunity(
    opportunity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a draft quotation from a won opportunity (client must exist)."""
    opportunity = (await db.execute(
        select(CRMOpportunity).where(
            CRMOpportunity.id == opportunity_id,
            CRMOpportunity.company_id == current_user.company_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if not opportunity:
        raise HTTPException(status_code=404, detail="გაყიდვების შესაძლებლობა არ მოიძებნა")
    if opportunity.stage != "won":
        raise HTTPException(status_code=400, detail="შემოთავაზება მხოლოდ მოგებული შესაძლებლობიდან იქმნება")
    if not opportunity.client_id:
        raise HTTPException(status_code=400, detail="შესაძლებლობას კლიენტი არ უკავშირდება — ჯერ გადაიყვანეთ ლიდი კლიენტად")

    from app.models.quotation import Quotation, QuotationItem

    today = utc_now().date()
    prefix = f"QT-{today.strftime('%Y%m%d')}"
    same_day = (await db.execute(select(func.count(Quotation.id)).where(
        Quotation.company_id == current_user.company_id,
        Quotation.quotation_number.like(f"{prefix}-%"),
    ))).scalar_one()
    number = f"{prefix}-{same_day + 1:03d}"

    subtotal = opportunity.amount
    vat = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
    total = subtotal + vat

    q = Quotation(
        company_id=current_user.company_id,
        client_id=opportunity.client_id,
        quotation_number=number,
        quotation_date=today,
        valid_until=None,
        status="draft",
        currency="GEL",
        subtotal=subtotal,
        vat_amount=vat,
        total=total,
        discount_percent=Decimal("0"),
        notes=opportunity.notes,
        created_by=current_user.id,
    )
    db.add(q)
    await db.flush()
    db.add(QuotationItem(
        quotation_id=q.id,
        product_id=None,
        line_number=1,
        description=opportunity.name,
        quantity=Decimal("1"),
        unit_price=subtotal,
        discount_percent=Decimal("0"),
        line_total=subtotal,
    ))
    add_audit(db, current_user, "crm.quotation_created_from_opportunity", "quotation", q.id, {
        "opportunity_id": str(opportunity.id),
        "number": number,
    })
    await db.commit()
    return ResponseBase(data={"quotation_id": str(q.id), "quotation_number": number, "status": "draft"})


@router.post("/quotations/{quotation_id}/send-email", response_model=ResponseBase[dict])
async def send_quotation_email(
    quotation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a quotation to the client's email (SMTP or sandbox email_messages)."""
    from app.models.email_calendar import EmailMessage
    from app.models.quotation import Quotation
    from app.services.email_service import send_email_smtp, smtp_configured

    q = (await db.execute(
        select(Quotation).where(Quotation.id == quotation_id, Quotation.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="შემოთავაზება არ მოიძებნა")
    client = (await db.execute(select(Client).where(Client.id == q.client_id))).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")
    contact = (await db.execute(
        select(Contact).where(Contact.client_id == client.id, Contact.is_primary.is_(True))
    )).scalar_one_or_none()
    to_email = (contact.email if contact else None) or client.email
    if not to_email:
        raise HTTPException(status_code=400, detail="კლიენტს ელფოსტა არ აქვს მითითებული")

    subject = f"კომერციული შემოთავაზება {q.quotation_number}"
    body = (
        f"გამარჯობა,\n\n"
        f"გთავაზობთ კომერციულ შემოთავაზებას {q.quotation_number}.\n"
        f"თანხა: {q.total:.2f} GEL (დღგ-ს ჩათვლით)\n"
        f"მოქმედების ვადა: {q.valid_until or 'არ არის მითითებული'}\n\n"
        f"პატივისცემით,\n{current_user.full_name or current_user.email}"
    )
    status_value = "sent"
    if smtp_configured():
        try:
            send_email_smtp(to_email, subject, body)
        except Exception:
            status_value = "failed"
    db.add(EmailMessage(
        company_id=current_user.company_id,
        to_email=to_email,
        subject=subject,
        body=body,
        status=status_value,
    ))
    if status_value == "sent" and q.status == "draft":
        q.status = "sent"
    add_audit(db, current_user, "quotation.email_sent", "quotation", q.id, {
        "to_email": to_email, "status": status_value,
    })
    await db.commit()
    return ResponseBase(data={"to_email": to_email, "status": status_value})


# ── CRM 2.0 — enterprise: contacts / email threads / telephony / attribution / routing / SLA / territory / GDPR ──


@router.get("/contacts", response_model=ResponseBase[list[dict]])
async def list_contacts(
    client_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [CRMContact.company_id == current_user.company_id]
    if client_id:
        filters.append(CRMContact.client_id == client_id)
    rows = (await db.execute(
        select(CRMContact).where(*filters).order_by(CRMContact.last_name, CRMContact.first_name)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(c.id), "client_id": str(c.client_id), "first_name": c.first_name,
        "last_name": c.last_name, "email": c.email, "phone": c.phone, "mobile": c.mobile,
        "job_title": c.job_title, "department": c.department, "is_primary": c.is_primary,
        "is_active": c.is_active,
    } for c in rows])


@router.post("/contacts", response_model=ResponseBase[dict], status_code=201)
async def create_contact(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = (await db.execute(select(Client).where(
        Client.id == data.get("client_id"), Client.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")
    c = CRMContact(
        company_id=current_user.company_id, client_id=data["client_id"],
        first_name=data["first_name"], last_name=data["last_name"],
        email=data.get("email"), phone=data.get("phone"), mobile=data.get("mobile"),
        job_title=data.get("job_title"), department=data.get("department"),
        is_primary=data.get("is_primary", False),
    )
    db.add(c)
    await db.flush()
    await db.commit()
    return ResponseBase(data={"id": str(c.id)}, message="კონტაქტი შეიქმნა")


@router.post("/email-threads", response_model=ResponseBase[dict], status_code=201)
async def create_email_thread(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full email thread: create thread + first message."""
    thread = CRMEmailThread(
        company_id=current_user.company_id, lead_id=data.get("lead_id"),
        client_id=data.get("client_id"), subject=data["subject"],
    )
    db.add(thread)
    await db.flush()
    db.add(CRMEmailMessage(
        thread_id=thread.id, direction=data.get("direction", "inbound"),
        from_email=data["from_email"], to_email=data["to_email"],
        subject=data["subject"], body=data.get("body"), message_id=data.get("message_id"),
    ))
    await db.commit()
    return ResponseBase(data={"id": str(thread.id)}, message="ელ.ფოსტის thread შეიქმნა")


@router.get("/email-threads/{thread_id}/messages", response_model=ResponseBase[list[dict]])
async def list_email_messages(
    thread_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = (await db.execute(select(CRMEmailThread).where(
        CRMEmailThread.id == thread_id, CRMEmailThread.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread არ მოიძებნა")
    rows = (await db.execute(
        select(CRMEmailMessage).where(CRMEmailMessage.thread_id == thread.id).order_by(CRMEmailMessage.sent_at)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(m.id), "direction": m.direction, "from_email": m.from_email,
        "to_email": m.to_email, "subject": m.subject, "body": m.body,
        "sent_at": m.sent_at.isoformat(),
    } for m in rows])


@router.post("/telephony/calls", response_model=ResponseBase[dict], status_code=201)
async def log_telephony_call(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Telephony: log a call (inbound/outbound) with duration and recording."""
    call = CRMTelephonyCall(
        company_id=current_user.company_id, lead_id=data.get("lead_id"),
        client_id=data.get("client_id"), contact_id=data.get("contact_id"),
        direction=data.get("direction", "inbound"), phone_number=data["phone_number"],
        duration_seconds=int(data.get("duration_seconds", 0)),
        status=data.get("status", "completed"), recording_url=data.get("recording_url"),
        notes=data.get("notes"),
    )
    db.add(call)
    await db.flush()
    await db.commit()
    return ResponseBase(data={"id": str(call.id)}, message="ზარი დაფიქსირდა")


@router.get("/telephony/calls", response_model=ResponseBase[list[dict]])
async def list_telephony_calls(
    lead_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [CRMTelephonyCall.company_id == current_user.company_id]
    if lead_id:
        filters.append(CRMTelephonyCall.lead_id == lead_id)
    rows = (await db.execute(
        select(CRMTelephonyCall).where(*filters).order_by(CRMTelephonyCall.started_at.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(c.id), "lead_id": str(c.lead_id) if c.lead_id else None,
        "direction": c.direction, "phone_number": c.phone_number,
        "duration_seconds": c.duration_seconds, "status": c.status,
        "recording_url": c.recording_url, "notes": c.notes,
        "started_at": c.started_at.isoformat(),
    } for c in rows])


@router.post("/attribution", response_model=ResponseBase[dict], status_code=201)
async def create_attribution(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marketing campaign attribution: lead/opportunity → campaign."""
    att = CRMCampaignAttribution(
        company_id=current_user.company_id, lead_id=data.get("lead_id"),
        opportunity_id=data.get("opportunity_id"), campaign=data["campaign"],
        channel=data.get("channel", "email"),
    )
    db.add(att)
    await db.flush()
    await db.commit()
    return ResponseBase(data={"id": str(att.id)}, message="ატრიბუცია დაფიქსირდა")


@router.get("/attribution/analytics", response_model=ResponseBase[dict])
async def attribution_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Campaign attribution analytics: leads per campaign/channel."""
    rows = (await db.execute(
        select(CRMCampaignAttribution).where(CRMCampaignAttribution.company_id == current_user.company_id)
    )).scalars().all()
    by_campaign: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    for a in rows:
        by_campaign[a.campaign] = by_campaign.get(a.campaign, 0) + 1
        by_channel[a.channel] = by_channel.get(a.channel, 0) + 1
    return ResponseBase(data={
        "by_campaign": by_campaign, "by_channel": by_channel, "total": len(rows),
    })


@router.post("/routing/run", response_model=ResponseBase[dict])
async def run_lead_routing(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lead routing: assign a new lead to an owner by strategy (round_robin | least_loaded | territory)."""
    lead_id = data.get("lead_id")
    lead = (await db.execute(select(CRMLead).where(
        CRMLead.id == lead_id, CRMLead.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="ლიდი არ მოიძებნა")
    if lead.owner_id:
        return ResponseBase(data={"lead_id": str(lead.id), "owner_id": str(lead.owner_id), "strategy": "already_assigned"})

    rules = (await db.execute(
        select(CRMRoutingRule).where(
            CRMRoutingRule.company_id == current_user.company_id, CRMRoutingRule.is_active.is_(True),
        )
    )).scalars().all()
    if not rules:
        raise HTTPException(status_code=400, detail="როუტინგის წესი არ არის კონფიგურირებული")
    rule = rules[0]

    from app.models.user import User as CRMUser
    users = (await db.execute(
        select(CRMUser).where(CRMUser.company_id == current_user.company_id, CRMUser.is_active.is_(True))
    )).scalars().all()
    if not users:
        raise HTTPException(status_code=400, detail="აქტიური მომხმარებელი არ არის")

    if rule.strategy == "least_loaded":
        counts: dict[uuid.UUID, int] = {}
        for u in users:
            n = (await db.execute(select(func.count(CRMLead.id)).where(
                CRMLead.owner_id == u.id, CRMLead.status.notin_(["converted", "lost"]),
            ))).scalar_one()
            counts[u.id] = n
        owner = min(users, key=lambda u: counts[u.id])
    elif rule.strategy == "territory" and rule.territory_id:
        terr = (await db.execute(select(CRMTerritory).where(CRMTerritory.id == rule.territory_id))).scalar_one_or_none()
        owner = next((u for u in users if u.id == (terr.owner_id if terr else None)), users[0])
    else:  # round_robin
        last = (await db.execute(
            select(CRMLead.owner_id).where(CRMLead.company_id == current_user.company_id, CRMLead.owner_id.isnot(None))
            .order_by(CRMLead.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        idx = 0
        if last:
            for i, u in enumerate(users):
                if u.id == last:
                    idx = (i + 1) % len(users)
                    break
        owner = users[idx]

    lead.owner_id = owner.id
    await db.commit()
    return ResponseBase(data={"lead_id": str(lead.id), "owner_id": str(owner.id), "strategy": rule.strategy})


@router.get("/territories", response_model=ResponseBase[list[dict]])
async def list_territories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(CRMTerritory).where(CRMTerritory.company_id == current_user.company_id).order_by(CRMTerritory.name)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(t.id), "name": t.name, "region": t.region,
        "owner_id": str(t.owner_id) if t.owner_id else None, "is_active": t.is_active,
    } for t in rows])


@router.post("/territories", response_model=ResponseBase[dict], status_code=201)
async def create_territory(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = CRMTerritory(
        company_id=current_user.company_id, name=data["name"],
        region=data.get("region"), owner_id=data.get("owner_id"),
    )
    db.add(t)
    await db.flush()
    await db.commit()
    return ResponseBase(data={"id": str(t.id)}, message="ტერიტორია შეიქმნა")


@router.get("/slas", response_model=ResponseBase[list[dict]])
async def list_slas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(CRMSLA).where(CRMSLA.company_id == current_user.company_id).order_by(CRMSLA.priority)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(s.id), "name": s.name, "priority": s.priority,
        "response_hours": s.response_hours, "resolution_hours": s.resolution_hours,
        "is_active": s.is_active,
    } for s in rows])


@router.post("/slas", response_model=ResponseBase[dict], status_code=201)
async def create_sla(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sla = CRMSLA(
        company_id=current_user.company_id, name=data["name"],
        priority=data.get("priority", "normal"),
        response_hours=int(data.get("response_hours", 24)),
        resolution_hours=int(data.get("resolution_hours", 72)),
    )
    db.add(sla)
    await db.flush()
    await db.commit()
    return ResponseBase(data={"id": str(sla.id)}, message="SLA შეიქმნა")


@router.post("/gdpr/consents", response_model=ResponseBase[dict], status_code=201)
async def set_gdpr_consent(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GDPR/თანხმობების მართვა: grant/revoke consent for a lead or contact."""
    from app.core.time import utc_now
    existing = (await db.execute(select(CRMGdprConsent).where(
        CRMGdprConsent.company_id == current_user.company_id,
        CRMGdprConsent.consent_type == data["consent_type"],
        CRMGdprConsent.lead_id == data.get("lead_id"),
        CRMGdprConsent.contact_id == data.get("contact_id"),
    ))).scalar_one_or_none()
    granted = bool(data.get("granted", True))
    now = utc_now()
    if existing:
        existing.granted = granted
        existing.granted_at = now if granted else existing.granted_at
        existing.revoked_at = None if granted else now
    else:
        existing = CRMGdprConsent(
            company_id=current_user.company_id, lead_id=data.get("lead_id"),
            contact_id=data.get("contact_id"), consent_type=data["consent_type"],
            granted=granted, granted_at=now if granted else None,
            revoked_at=None if granted else now, source=data.get("source"),
        )
        db.add(existing)
    await db.flush()
    await db.commit()
    return ResponseBase(data={"id": str(existing.id), "granted": granted}, message="თანხმობა განახლდა")


@router.get("/gdpr/consents", response_model=ResponseBase[list[dict]])
async def list_gdpr_consents(
    lead_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [CRMGdprConsent.company_id == current_user.company_id]
    if lead_id:
        filters.append(CRMGdprConsent.lead_id == lead_id)
    rows = (await db.execute(
        select(CRMGdprConsent).where(*filters).order_by(CRMGdprConsent.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(c.id), "lead_id": str(c.lead_id) if c.lead_id else None,
        "contact_id": str(c.contact_id) if c.contact_id else None,
        "consent_type": c.consent_type, "granted": c.granted,
        "granted_at": c.granted_at.isoformat() if c.granted_at else None,
        "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
        "source": c.source,
    } for c in rows])

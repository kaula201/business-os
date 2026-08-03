from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.client import Client, ClientStatus, Contact
from app.models.crm import CRMActivity, CRMLead, CRMOpportunity
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
)

router = APIRouter(prefix="/crm", tags=["CRM — ლიდები და გაყიდვები"])


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
    lead = CRMLead(
        company_id=current_user.company_id,
        owner_id=data.owner_id or current_user.id,
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
    db.add(lead)
    await db.flush()
    add_audit(db, current_user, "crm.lead_created", "crm_lead", lead.id, {
        "company_name": lead.company_name,
        "source": lead.source,
        "estimated_value": lead.estimated_value,
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
    before_status = lead.status
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "email" and value is not None:
            value = str(value)
        setattr(lead, field, value)
    # Track last activity on any update
    lead.last_activity_at = utc_now()
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
    opportunity = CRMOpportunity(
        company_id=current_user.company_id,
        lead_id=data.lead_id,
        client_id=data.client_id,
        owner_id=data.owner_id or current_user.id,
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
    before_stage = opportunity.stage
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(opportunity, field, value)
    if opportunity.stage == "won" and "probability" not in data.model_fields_set:
        opportunity.probability = 100
    if opportunity.stage == "lost" and "probability" not in data.model_fields_set:
        opportunity.probability = 0
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

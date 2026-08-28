from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.time import utc_now
from app.models.client import Client, ClientStatus, Contact, Interaction
from app.models.accounting_controls import FiscalPosition
from app.models.user import User
from app.schemas.client import (
    ClientCreate,
    ClientListResponse,
    ClientResponse,
    ClientUpdate,
    ContactCreate,
    ContactResponse,
    InteractionCreate,
    InteractionResponse,
)
from app.schemas.common import PaginatedResponse, ResponseBase

router = APIRouter(prefix="/clients", tags=["CRM — კლიენტები"])


def primary_contact(client: Client) -> Contact | None:
    return next((contact for contact in client.contacts if contact.is_primary), None) or (
        client.contacts[0] if client.contacts else None
    )


async def validate_fiscal_position(db: AsyncSession, fiscal_position_id: UUID | None, company_id: UUID) -> None:
    if fiscal_position_id is None:
        return
    found = (await db.execute(select(FiscalPosition.id).where(
        FiscalPosition.id == fiscal_position_id,
        FiscalPosition.company_id == company_id,
        FiscalPosition.is_active.is_(True),
        FiscalPosition.applies_to.in_(["sale", "both"]),
    ))).scalar_one_or_none()
    if found is None:
        raise HTTPException(status_code=422, detail="Fiscal Position არ მოიძებნა ან ამ კომპანიის არაა")


def build_client_response(client: Client) -> ClientResponse:
    primary = primary_contact(client)
    return ClientResponse(
        id=client.id,
        company_id=client.company_id,
        client_type=client.client_type,
        name=client.name,
        identification_code=client.identification_code,
        is_vat_payer=client.vat_status,
        fiscal_position_id=client.fiscal_position_id,
        address=client.address,
        phone=primary.phone if primary else None,
        email=primary.email if primary else None,
        status=client.status,
        notes=client.notes,
        contacts=[ContactResponse.model_validate(contact) for contact in client.contacts],
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


@router.get("/", response_model=ResponseBase[PaginatedResponse[ClientListResponse]])
async def list_clients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    client_type: Optional[str] = None,
    search: Optional[str] = None,
    has_debt: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Client)
        .where(
            Client.company_id == current_user.company_id,
            Client.deleted_at.is_(None),
        )
        .options(selectinload(Client.contacts))
    )

    if status:
        query = query.where(Client.status == status)
    if client_type:
        query = query.where(Client.client_type == client_type)
    if search:
        query = query.where(
            Client.name.ilike(f"%{search}%")
            | Client.identification_code.ilike(f"%{search}%")
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = (
        query.order_by(Client.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    clients = (await db.execute(query)).unique().scalars().all()

    items = []
    for client in clients:
        primary = primary_contact(client)
        items.append(
            ClientListResponse(
                id=client.id,
                company_id=client.company_id,
                name=client.name,
                client_type=client.client_type,
                identification_code=client.identification_code,
                is_vat_payer=client.vat_status,
                address=client.address,
                phone=primary.phone if primary else None,
                email=primary.email if primary else None,
                status=client.status,
                notes=client.notes,
                created_at=client.created_at,
                updated_at=client.updated_at,
                primary_contact=primary.full_name if primary else None,
                primary_phone=primary.phone if primary else None,
                last_order_date=None,
                total_debt=0,
            )
        )

    return ResponseBase(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )
    )


@router.get("/{client_id}", response_model=ResponseBase[ClientResponse])
async def get_client(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Client)
        .where(
            Client.id == client_id,
            Client.company_id == current_user.company_id,
            Client.deleted_at.is_(None),
        )
        .options(selectinload(Client.contacts))
    )
    client = result.unique().scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")
    return ResponseBase(data=build_client_response(client))


@router.post("/", response_model=ResponseBase[ClientResponse])
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(Client).where(
            Client.company_id == current_user.company_id,
            Client.identification_code == data.identification_code,
            Client.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400, detail="საიდენტიფიკაციო კოდი უკვე არსებობს"
        )
    await validate_fiscal_position(db, data.fiscal_position_id, current_user.company_id)

    client = Client(
        company_id=current_user.company_id,
        client_type=data.client_type,
        name=data.name,
        identification_code=data.identification_code,
        vat_status=data.is_vat_payer,
        fiscal_position_id=data.fiscal_position_id,
        address=data.address,
        status=ClientStatus.POTENTIAL,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(client)
    await db.flush()

    contacts = list(data.contacts)
    if data.phone or data.email:
        contacts.insert(
            0,
            ContactCreate(
                full_name=data.name,
                phone=data.phone,
                email=data.email,
                is_primary=True,
            ),
        )

    for index, contact_data in enumerate(contacts):
        db.add(
            Contact(
                client_id=client.id,
                full_name=contact_data.full_name,
                position=contact_data.position,
                phone=contact_data.phone,
                email=str(contact_data.email) if contact_data.email else None,
                is_primary=contact_data.is_primary or index == 0,
            )
        )

    await db.flush()
    created = (
        await db.execute(
            select(Client)
            .where(Client.id == client.id)
            .options(selectinload(Client.contacts))
        )
    ).unique().scalar_one()
    return ResponseBase(data=build_client_response(created))


@router.patch("/{client_id}", response_model=ResponseBase[ClientResponse])
async def update_client(
    client_id: UUID,
    data: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Client)
        .where(
            Client.id == client_id,
            Client.company_id == current_user.company_id,
            Client.deleted_at.is_(None),
        )
        .options(selectinload(Client.contacts))
    )
    client = result.unique().scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    phone_supplied = "phone" in update_data
    email_supplied = "email" in update_data
    phone = update_data.pop("phone", None)
    email = update_data.pop("email", None)
    vat_status = update_data.pop("is_vat_payer", None)
    if "fiscal_position_id" in update_data:
        await validate_fiscal_position(db, update_data["fiscal_position_id"], current_user.company_id)

    # Audit: capture old values before mutation (P1.7)
    audit_fields = ["name", "email", "phone", "client_type", "vat_status", "credit_limit", "balance", "status"]
    before = {f: getattr(client, f, None) for f in audit_fields}
    from app.services.audit_service import audit_changes

    if vat_status is not None:
        client.vat_status = vat_status
    for field, value in update_data.items():
        setattr(client, field, value)

    if phone_supplied or email_supplied:
        primary = primary_contact(client)
        if primary is None:
            primary = Contact(
                client_id=client.id,
                full_name=client.name,
                is_primary=True,
            )
            db.add(primary)
            client.contacts.append(primary)
        if phone_supplied:
            primary.phone = phone
        if email_supplied:
            primary.email = str(email) if email else None

    # Audit: record what changed (old vs new)
    after = {f: getattr(client, f, None) for f in audit_fields}
    if phone_supplied:
        before["phone"] = None
        after["phone"] = phone
    if email_supplied:
        before["email"] = None
        after["email"] = str(email) if email else None
    await audit_changes(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        action="update",
        entity_type="client",
        entity_id=client.id,
        entity_label=client.name,
        before=before,
        after=after,
        fields=audit_fields,
    )

    await db.flush()
    await db.refresh(client, attribute_names=["updated_at"])
    return ResponseBase(data=build_client_response(client))


@router.delete("/{client_id}", response_model=ResponseBase[dict])
async def delete_client(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("clients", "can_delete")),
):
    result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.company_id == current_user.company_id,
            Client.deleted_at.is_(None),
        )
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")

    client.deleted_at = utc_now()
    client.status = ClientStatus.INACTIVE
    await db.flush()
    return ResponseBase(data={"message": "კლიენტი წაშლილია"})


@router.post(
    "/{client_id}/interactions",
    response_model=ResponseBase[InteractionResponse],
)
async def add_interaction(
    client_id: UUID,
    data: InteractionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.company_id == current_user.company_id,
            Client.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")

    interaction = Interaction(
        client_id=client_id,
        user_id=current_user.id,
        type=data.type,
        description=data.description,
    )
    db.add(interaction)
    await db.flush()
    await db.refresh(interaction)
    return ResponseBase(
        data=InteractionResponse(
            id=interaction.id,
            type=interaction.type,
            description=interaction.description,
            created_by=interaction.user_id,
            created_at=interaction.created_at,
        )
    )

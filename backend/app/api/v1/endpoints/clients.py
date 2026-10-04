from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.georgia import validate_identification_code
from app.core.time import utc_now
from app.models.client import Client, ClientStatus, ClientType, Contact, Interaction, ClientAddress, ClientGroupDef, ClientRelation, client_groups
from app.models.accounting_controls import FiscalPosition
from app.models.user import User
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.task import Task
from app.models.receivable import CustomerPayment, CustomerReceivable, CustomerCreditNote
from app.schemas.client import (
    ClientCreate,
    ClientListResponse,
    ClientResponse,
    ClientUpdate,
    ContactCreate,
    ContactResponse,
    InteractionCreate,
    InteractionResponse,
    AddressCreate,
    AddressResponse,
    GroupCreate,
    GroupResponse,
    RelationCreate,
    RelationResponse,
    ClientStatement,
    StatementLine,
    MergeRequest,
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


def build_client_response(client: Client, full_identification: bool = True) -> ClientResponse:
    primary = primary_contact(client)
    identification_code = client.identification_code
    if (
        not full_identification
        and client.client_type == ClientType.INDIVIDUAL.value
        and len(identification_code) == 11
    ):
        identification_code = (
            identification_code[:3] + "*****" + identification_code[-3:]
        )
    return ClientResponse(
        id=client.id,
        company_id=client.company_id,
        client_type=client.client_type,
        name=client.name,
        identification_code=identification_code,
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
        identification_code = client.identification_code
        if client.client_type == ClientType.INDIVIDUAL.value and len(identification_code) == 11:
            identification_code = (
                identification_code[:3] + "*****" + identification_code[-3:]
            )
        items.append(
            ClientListResponse(
                id=client.id,
                company_id=client.company_id,
                name=client.name,
                client_type=client.client_type,
                identification_code=identification_code,
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


@router.get("/client-groups", response_model=ResponseBase[list[GroupResponse]])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    groups = (await db.execute(
        select(ClientGroupDef).where(ClientGroupDef.company_id == current_user.company_id)
        .order_by(ClientGroupDef.name)
    )).scalars().all()
    out = []
    for g in groups:
        cnt = (await db.execute(
            select(func.count()).select_from(Client).join(Client.groups).where(ClientGroupDef.id == g.id, Client.deleted_at.is_(None))
        )).scalar() or 0
        out.append(GroupResponse(id=g.id, name=g.name, description=g.description, color=g.color, client_count=cnt))
    return ResponseBase(data=out)



@router.post("/client-groups", response_model=ResponseBase[GroupResponse])
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    g = ClientGroupDef(company_id=current_user.company_id, name=data.name, description=data.description, color=data.color)
    db.add(g)
    await db.flush()
    await db.refresh(g)
    return ResponseBase(data=GroupResponse(id=g.id, name=g.name, description=g.description, color=g.color, client_count=0))



@router.delete("/client-groups/{group_id}")
async def delete_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    g = (await db.execute(select(ClientGroupDef).where(ClientGroupDef.id == group_id, ClientGroupDef.company_id == current_user.company_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="ჯგუფი არ მოიძებნა")
    await db.delete(g)
    await db.commit()
    return ResponseBase(data={"ok": True})



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

    can_view_full = current_user.role == User.Role.ADMIN
    if not can_view_full:
        try:
            await require_module("clients", "can_edit")(db=db, current_user=current_user)
            can_view_full = True
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
    return ResponseBase(data=build_client_response(client, full_identification=can_view_full))


@router.post("/", response_model=ResponseBase[ClientResponse])
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_person = data.client_type == ClientType.INDIVIDUAL
    data.identification_code = validate_identification_code(
        data.identification_code, is_person
    )

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
        credit_limit=data.credit_limit,
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
    client_type = update_data.get("client_type", client.client_type)
    is_person = client_type == ClientType.INDIVIDUAL or client_type == ClientType.INDIVIDUAL.value
    if "identification_code" in update_data:
        update_data["identification_code"] = validate_identification_code(
            update_data["identification_code"], is_person
        )
    else:
        validate_identification_code(client.identification_code, is_person)
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


# ── Client 2.0: addresses, groups, relations, statement, merge ────────────────




@router.post("/{client_id}/groups", response_model=ResponseBase[list[GroupResponse]])
async def set_client_groups(
    client_id: UUID,
    group_ids: list[UUID],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.company_id == current_user.company_id, Client.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")
    groups = (await db.execute(
        select(ClientGroupDef).where(ClientGroupDef.id.in_(group_ids), ClientGroupDef.company_id == current_user.company_id)
    )).scalars().all()
    # replace M2M rows directly (avoids async lazy-load on client.groups)
    await db.execute(client_groups.delete().where(client_groups.c.client_id == client_id))
    for g in groups:
        await db.execute(client_groups.insert().values(client_id=client_id, group_id=g.id))
    await db.commit()
    return ResponseBase(data=[GroupResponse(id=g.id, name=g.name, description=g.description, color=g.color) for g in groups])


@router.get("/{client_id}/addresses", response_model=ResponseBase[list[AddressResponse]])
async def list_addresses(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.company_id == current_user.company_id, Client.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")
    addrs = (await db.execute(select(ClientAddress).where(ClientAddress.client_id == client_id).order_by(ClientAddress.is_default.desc(), ClientAddress.created_at))).scalars().all()
    return ResponseBase(data=[AddressResponse.model_validate(a) for a in addrs])


@router.post("/{client_id}/addresses", response_model=ResponseBase[AddressResponse])
async def create_address(
    client_id: UUID,
    data: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.company_id == current_user.company_id, Client.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")
    if data.is_default:
        await db.execute(
            ClientAddress.__table__.update().where(ClientAddress.client_id == client_id).values(is_default=False)
        )
    a = ClientAddress(client_id=client_id, **data.model_dump())
    db.add(a)
    await db.flush()
    await db.refresh(a)
    await db.commit()
    return ResponseBase(data=AddressResponse.model_validate(a))


@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = (await db.execute(
        select(ClientAddress).join(Client).where(
            ClientAddress.id == address_id, Client.company_id == current_user.company_id
        )
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="მისამართი არ მოიძებნა")
    await db.delete(a)
    await db.commit()
    return ResponseBase(data={"ok": True})


@router.get("/{client_id}/relations", response_model=ResponseBase[list[RelationResponse]])
async def list_relations(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rels = (await db.execute(
        select(ClientRelation, Client.name).join(Client, Client.id == ClientRelation.related_client_id).where(
            ClientRelation.client_id == client_id, ClientRelation.company_id == current_user.company_id
        )
    )).all()
    return ResponseBase(data=[RelationResponse(id=r.id, related_client_id=r.related_client_id, related_client_name=name, relation_type=r.relation_type, notes=r.notes) for r, name in rels])


@router.post("/{client_id}/relations", response_model=ResponseBase[RelationResponse])
async def create_relation(
    client_id: UUID,
    data: RelationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.related_client_id == client_id:
        raise HTTPException(status_code=400, detail="კლიენტი თავის თავს ვერ დაუკავშირდება")
    related = (await db.execute(
        select(Client).where(Client.id == data.related_client_id, Client.company_id == current_user.company_id, Client.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not related:
        raise HTTPException(status_code=404, detail="დაკავშირებული კლიენტი არ მოიძებნა")
    existing = (await db.execute(
        select(ClientRelation).where(ClientRelation.client_id == client_id, ClientRelation.related_client_id == data.related_client_id)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="კავშირი უკვე არსებობს")
    r = ClientRelation(company_id=current_user.company_id, client_id=client_id, related_client_id=data.related_client_id, relation_type=data.relation_type, notes=data.notes)
    db.add(r)
    await db.flush()
    await db.refresh(r)
    await db.commit()
    return ResponseBase(data=RelationResponse(id=r.id, related_client_id=r.related_client_id, related_client_name=related.name, relation_type=r.relation_type, notes=r.notes))


@router.delete("/relations/{relation_id}")
async def delete_relation(
    relation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = (await db.execute(
        select(ClientRelation).where(ClientRelation.id == relation_id, ClientRelation.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="კავშირი არ მოიძებნა")
    await db.delete(r)
    await db.commit()
    return ResponseBase(data={"ok": True})


@router.get("/{client_id}/statement", response_model=ResponseBase[ClientStatement])
async def client_statement(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full statement: opening balance, invoices, payments, credit notes, running balance."""
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.company_id == current_user.company_id, Client.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")

    invoices = (await db.execute(
        select(Invoice).where(Invoice.company_id == current_user.company_id, Invoice.client_id == client_id)
        .order_by(Invoice.created_at)
    )).scalars().all()
    payments = (await db.execute(
        select(CustomerPayment).join(CustomerReceivable).where(
            CustomerReceivable.company_id == current_user.company_id,
            CustomerReceivable.client_id == client_id,
        ).order_by(CustomerPayment.created_at)
    )).scalars().all()
    credit_notes = (await db.execute(
        select(CustomerCreditNote).join(CustomerReceivable).where(
            CustomerReceivable.company_id == current_user.company_id,
            CustomerReceivable.client_id == client_id,
        ).order_by(CustomerCreditNote.created_at)
    )).scalars().all()

    lines: list[StatementLine] = []
    for inv in invoices:
        lines.append(StatementLine(date=inv.created_at, type="invoice", reference=inv.invoice_number, description=f"ინვოისი {inv.invoice_number}", debit=float(inv.total or 0), credit=0.0))
    for p in payments:
        lines.append(StatementLine(date=p.created_at, type="payment", reference=str(p.id)[:8], description="გადახდა", debit=0.0, credit=float(p.amount or 0)))
    for cn in credit_notes:
        lines.append(StatementLine(date=cn.created_at, type="credit_note", reference=str(cn.id)[:8], description="საკრედიტო ნოტა", debit=0.0, credit=float(cn.amount or 0)))

    lines.sort(key=lambda l: l.date)
    balance = 0.0
    for l in lines:
        balance += l.debit - l.credit
        l.balance = round(balance, 2)

    total_invoiced = sum(l.debit for l in lines)
    total_paid = sum(l.credit for l in lines)
    return ResponseBase(data=ClientStatement(
        client_id=client_id, client_name=client.name,
        opening_balance=0.0, lines=lines, closing_balance=round(balance, 2),
        total_invoiced=round(total_invoiced, 2), total_paid=round(total_paid, 2),
    ))


@router.post("/merge", response_model=ResponseBase[ClientResponse])
async def merge_clients(
    data: MergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Merge duplicate clients: move orders/invoices/receivables/contacts to target, soft-delete sources."""
    if data.target_client_id in data.source_client_ids:
        raise HTTPException(status_code=400, detail="სამიზნე კლიენტი არ შეიძლება იყოს წყაროებში")
    target = (await db.execute(
        select(Client).where(Client.id == data.target_client_id, Client.company_id == current_user.company_id, Client.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="სამიზნე კლიენტი არ მოიძებნა")
    sources = (await db.execute(
        select(Client).where(Client.id.in_(data.source_client_ids), Client.company_id == current_user.company_id, Client.deleted_at.is_(None))
    )).scalars().all()
    if len(sources) != len(data.source_client_ids):
        raise HTTPException(status_code=404, detail="ერთ-ერთი წყარო კლიენტი არ მოიძებნა")

    for src in sources:
        # move orders
        await db.execute(Order.__table__.update().where(Order.client_id == src.id).values(client_id=target.id))
        # move invoices
        await db.execute(Invoice.__table__.update().where(Invoice.client_id == src.id).values(client_id=target.id))
        # move receivables
        await db.execute(CustomerReceivable.__table__.update().where(CustomerReceivable.client_id == src.id).values(client_id=target.id))
        # move contacts
        await db.execute(Contact.__table__.update().where(Contact.client_id == src.id).values(client_id=target.id))
        # move addresses
        await db.execute(ClientAddress.__table__.update().where(ClientAddress.client_id == src.id).values(client_id=target.id))
        # move tasks
        await db.execute(Task.__table__.update().where(Task.client_id == src.id).values(client_id=target.id))
        # soft delete source
        src.deleted_at = utc_now()

    await db.commit()
    # reload with relationships to avoid async lazy-load in response serialization
    target = (await db.execute(
        select(Client).options(selectinload(Client.contacts)).where(Client.id == target.id)
    )).scalar_one()
    return ResponseBase(data=build_client_response(target))

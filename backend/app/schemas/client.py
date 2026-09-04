# backend/app/schemas/client.py
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models.client import Client, ClientType, ClientStatus


class ContactCreate(BaseModel):
    full_name: str
    position: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    is_primary: bool = False


class ContactResponse(BaseModel):
    id: UUID
    full_name: str
    position: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    is_primary: bool

    model_config = ConfigDict(from_attributes=True)


class ClientCreate(BaseModel):
    client_type: ClientType
    name: str = Field(..., min_length=2)
    identification_code: str
    is_vat_payer: bool = True
    fiscal_position_id: UUID | None = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    notes: Optional[str] = None
    credit_limit: Optional[float] = Field(default=None, ge=0)
    contacts: List[ContactCreate] = Field(default_factory=list)


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    client_type: Optional[ClientType] = None
    identification_code: Optional[str] = None
    is_vat_payer: Optional[bool] = None
    fiscal_position_id: UUID | None = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[ClientStatus] = None
    credit_limit: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None


class ClientResponse(BaseModel):
    id: UUID
    company_id: UUID
    client_type: str
    name: str
    identification_code: str
    is_vat_payer: bool
    fiscal_position_id: UUID | None = None
    address: Optional[str]
    phone: Optional[str] = None
    email: Optional[str] = None
    status: str
    notes: Optional[str]
    contacts: List[ContactResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientListResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    client_type: str
    identification_code: str
    is_vat_payer: bool
    fiscal_position_id: UUID | None = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    primary_contact: Optional[str] = None
    primary_phone: Optional[str] = None
    last_order_date: Optional[datetime] = None
    total_debt: float = 0

    model_config = ConfigDict(from_attributes=True)


class InteractionCreate(BaseModel):
    type: str  # note, call, meeting, email
    description: str


class InteractionResponse(BaseModel):
    id: UUID
    type: str
    description: str
    created_by: Optional[UUID]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Client 2.0: addresses, groups, relations, statement, merge ───────────────

class AddressCreate(BaseModel):
    address_type: str = "legal"  # legal | delivery | billing
    address_line: str
    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = "საქართველო"
    is_default: bool = False


class AddressResponse(BaseModel):
    id: UUID
    address_type: str
    address_line: str
    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    color: Optional[str] = None


class GroupResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    client_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class RelationCreate(BaseModel):
    related_client_id: UUID
    relation_type: str = "branch"  # parent | subsidiary | branch | partner
    notes: Optional[str] = None


class RelationResponse(BaseModel):
    id: UUID
    related_client_id: UUID
    related_client_name: Optional[str] = None
    relation_type: str
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class StatementLine(BaseModel):
    date: datetime
    type: str  # invoice | payment | credit_note | opening
    reference: str
    description: str
    debit: float = 0.0
    credit: float = 0.0
    balance: float = 0.0


class ClientStatement(BaseModel):
    client_id: UUID
    client_name: str
    currency: str = "GEL"
    opening_balance: float = 0.0
    lines: List[StatementLine] = []
    closing_balance: float = 0.0
    total_invoiced: float = 0.0
    total_paid: float = 0.0


class MergeRequest(BaseModel):
    source_client_ids: List[UUID] = Field(..., min_length=1)
    target_client_id: UUID

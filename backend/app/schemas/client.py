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

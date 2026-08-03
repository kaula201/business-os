"""Company settings API: get/update company profile."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.company import Company
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/companies", tags=["კომპანია"])


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    identification_code: str
    address: str | None
    phone: str | None
    email: str | None
    website: str | None
    logo_url: str | None
    is_vat_payer: bool
    currency: str
    is_active: bool
    created_at: str
    updated_at: str


class CompanyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    logo_url: str | None = None
    is_vat_payer: bool | None = None
    currency: str | None = Field(None, min_length=3, max_length=3)


def _to_response(c: Company) -> CompanyResponse:
    return CompanyResponse(
        id=c.id, name=c.name, identification_code=c.identification_code,
        address=c.address, phone=c.phone, email=c.email, website=c.website,
        logo_url=c.logo_url, is_vat_payer=c.vat_status, currency=c.currency,
        is_active=c.is_active,
        created_at=c.created_at.isoformat() if c.created_at else "",
        updated_at=c.updated_at.isoformat() if c.updated_at else "",
    )


@router.get("/me", response_model=ResponseBase[CompanyResponse])
async def get_my_company(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    company = (
        await db.execute(select(Company).where(Company.id == current_user.company_id))
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="კომპანია არ მოიძებნა")
    return ResponseBase(data=_to_response(company))


@router.patch("/me", response_model=ResponseBase[CompanyResponse])
async def update_my_company(
    data: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != User.Role.ADMIN:
        raise HTTPException(status_code=403, detail="მხოლოდ ადმინისტრატორს შეუძლია კომპანიის რედაქტირება")
    company = (
        await db.execute(select(Company).where(Company.id == current_user.company_id).with_for_update())
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="კომპანია არ მოიძებნა")
    if data.name is not None:
        company.name = data.name.strip()
    if data.address is not None:
        company.address = data.address.strip() if data.address else None
    if data.phone is not None:
        company.phone = data.phone.strip() if data.phone else None
    if data.email is not None:
        company.email = data.email.strip() if data.email else None
    if data.website is not None:
        company.website = data.website.strip() if data.website else None
    if data.logo_url is not None:
        company.logo_url = data.logo_url.strip() if data.logo_url else None
    if data.is_vat_payer is not None:
        company.vat_status = data.is_vat_payer
    if data.currency is not None:
        company.currency = data.currency.strip().upper()
    await db.flush()
    await db.refresh(company)
    return ResponseBase(data=_to_response(company))

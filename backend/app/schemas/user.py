# backend/app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.user import User


class UserCreate(BaseModel):
    company_name: str = Field(..., min_length=2)
    full_name: str = Field(..., min_length=2)
    email: EmailStr
    password: str = Field(..., min_length=8)
    is_vat_payer: bool = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    custom_role_id: Optional[UUID] = None


class UserResponse(BaseModel):
    id: UUID
    company_id: UUID
    email: str
    full_name: str
    role: str
    custom_role_id: Optional[UUID] = None
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserInvite(BaseModel):
    email: EmailStr
    role: str = Field(default="employee")
    full_name: str = Field(..., min_length=2)
    custom_role_id: Optional[UUID] = None

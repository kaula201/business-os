from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

PORTAL_USER_STATUSES = {"active", "disabled"}


class PortalUserCreate(BaseModel):
    client_id: UUID
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    status: str = Field(default="active", max_length=20)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in PORTAL_USER_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(PORTAL_USER_STATUSES)}, got '{v}'"
            )
        return v


class PortalUserUpdate(BaseModel):
    client_id: UUID | None = None
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=20)
    last_login_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in PORTAL_USER_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(PORTAL_USER_STATUSES)}, got '{v}'"
            )
        return v


class PortalUserResponse(BaseModel):
    id: UUID
    company_id: UUID
    client_id: UUID
    email: str
    display_name: str
    status: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

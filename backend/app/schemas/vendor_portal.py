from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

VENDOR_PORTAL_USER_STATUSES = {"active", "disabled"}


class VendorPortalUserCreate(BaseModel):
    supplier_id: UUID
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    status: str = Field(default="active", max_length=20)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VENDOR_PORTAL_USER_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(VENDOR_PORTAL_USER_STATUSES)}, got '{v}'"
            )
        return v


class VendorPortalUserUpdate(BaseModel):
    supplier_id: UUID | None = None
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=20)
    last_login_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VENDOR_PORTAL_USER_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(VENDOR_PORTAL_USER_STATUSES)}, got '{v}'"
            )
        return v


class VendorPortalUserResponse(BaseModel):
    id: UUID
    company_id: UUID
    supplier_id: UUID
    email: str
    display_name: str
    status: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


JOB_STATUSES = {"draft", "open", "closed"}


class JobPostingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    employment_type: str | None = Field(default=None, max_length=50)
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    description: str | None = None
    status: str = Field(default="draft", max_length=20)

    @field_validator("salary_max")
    @classmethod
    def validate_salary_range(cls, v: Decimal | None, info) -> Decimal | None:
        if v is not None:
            salary_min = info.data.get("salary_min")
            if salary_min is not None and v < salary_min:
                raise ValueError("salary_max must be >= salary_min")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in JOB_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(JOB_STATUSES)}, got '{v}'"
            )
        return v


class JobPostingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    employment_type: str | None = Field(default=None, max_length=50)
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    description: str | None = None
    status: str | None = Field(default=None, max_length=20)

    @field_validator("salary_max")
    @classmethod
    def validate_salary_range(cls, v: Decimal | None, info) -> Decimal | None:
        if v is not None:
            salary_min = info.data.get("salary_min")
            if salary_min is not None and v < salary_min:
                raise ValueError("salary_max must be >= salary_min")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in JOB_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(JOB_STATUSES)}, got '{v}'"
            )
        return v


class JobPostingResponse(BaseModel):
    id: UUID
    company_id: UUID
    title: str
    department: str | None
    location: str | None
    employment_type: str | None
    salary_min: Decimal | None
    salary_max: Decimal | None
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

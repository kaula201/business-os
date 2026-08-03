from pydantic import BaseModel, Field
from typing import Optional, Any, Generic, TypeVar
from datetime import datetime
from uuid import UUID

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    page: int
    page_size: int
    items: list[T]


class ResponseBase(BaseModel, Generic[T]):
    data: T | None = None
    message: Optional[str] = None


class MessageResponse(BaseModel):
    message: str
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CurrencyRateCreate(BaseModel):
    from_currency: str = Field(..., min_length=3, max_length=3)
    to_currency: str = Field(..., min_length=3, max_length=3)
    rate_date: date
    rate: Decimal = Field(..., gt=0, max_digits=18, decimal_places=6)
    source: str = Field("manual", max_length=50)


class CurrencyRateResponse(BaseModel):
    id: UUID
    company_id: UUID
    from_currency: str
    to_currency: str
    rate_date: date
    rate: float
    source: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CurrencyConversionRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    from_currency: str = Field(..., min_length=3, max_length=3)
    to_currency: str = Field(..., min_length=3, max_length=3)
    rate_date: date | None = None


class CurrencyConversionResponse(BaseModel):
    from_currency: str
    to_currency: str
    amount: float
    converted_amount: float
    rate: float
    rate_date: date


class NBGSyncResponse(BaseModel):
    rate_date: date
    currencies_received: int
    rates_created: int
    rates_updated: int


class NBGSyncStatusResponse(BaseModel):
    enabled: bool
    schedule: str
    timezone: str
    status: str | None = None
    trigger: str | None = None
    last_run_at: datetime | None = None
    effective_date: date | None = None
    currencies_received: int = 0
    rates_created: int = 0
    rates_updated: int = 0
    error_message: str | None = None

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field

class DeferredScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    deferral_type: str = Field(..., pattern="^(revenue|expense)$")
    total_amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    start_date: date
    periods: int = Field(..., ge=1, le=120)
    source_gl_account_id: UUID
    recognition_gl_account_id: UUID
    notes: str | None = None

class DeferredRecognitionResponse(BaseModel):
    id: UUID
    period_no: int
    recognition_date: date
    amount: float
    status: str
    journal_entry_id: UUID | None
    recognized_at: datetime | None

class DeferredScheduleResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    deferral_type: str
    total_amount: float
    recognized_amount: float
    remaining_amount: float
    start_date: date
    periods: int
    source_gl_account_id: UUID
    source_gl_account_code: str
    source_gl_account_name: str
    recognition_gl_account_id: UUID
    recognition_gl_account_code: str
    recognition_gl_account_name: str
    status: str
    notes: str | None
    created_at: datetime
    recognitions: list[DeferredRecognitionResponse]

class RecognizeDueRequest(BaseModel):
    as_of_date: date

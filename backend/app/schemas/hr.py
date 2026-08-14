"""Pydantic schemas for HR / Payroll module."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Department ──────────────────────────────────────────────────────────────────

class DepartmentBase(BaseModel):
    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=255)
    parent_id: Optional[UUID] = None
    manager_id: Optional[UUID] = None
    description: Optional[str] = None
    budget: Optional[Decimal] = None
    is_active: bool = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    parent_id: Optional[UUID] = None
    manager_id: Optional[UUID] = None
    description: Optional[str] = None
    budget: Optional[Decimal] = None
    is_active: Optional[bool] = None


class DepartmentResponse(DepartmentBase):
    id: UUID
    company_id: UUID
    head_count: int = 0
    children_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DepartmentTreeNode(BaseModel):
    """Department with nested children for hierarchy display."""
    id: UUID
    code: str
    name: str
    parent_id: Optional[UUID] = None
    manager_id: Optional[UUID] = None
    description: Optional[str] = None
    head_count: int = 0
    is_active: bool = True
    children: list["DepartmentTreeNode"] = []

    model_config = {"from_attributes": True}


# ── Employee ────────────────────────────────────────────────────────────────────

class EmployeeBase(BaseModel):
    personal_number: str = Field(..., max_length=11)
    full_name: str = Field(..., max_length=255)
    position: str = Field(..., max_length=255)
    department_id: Optional[UUID] = None
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_name: Optional[str] = None
    contract_type: str = "permanent"
    status: str = "active"
    hire_date: date
    termination_date: Optional[date] = None
    probation_end_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    base_salary: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    salary_currency: str = "GEL"
    hourly_rate: Optional[Decimal] = None
    manager_id: Optional[UUID] = None
    notes: Optional[str] = None


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    position: Optional[str] = Field(None, max_length=255)
    department_id: Optional[UUID] = None
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_name: Optional[str] = None
    contract_type: Optional[str] = None
    status: Optional[str] = None
    termination_date: Optional[date] = None
    probation_end_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    base_salary: Optional[Decimal] = Field(None, max_digits=14, decimal_places=2)
    salary_currency: Optional[str] = None
    hourly_rate: Optional[Decimal] = None
    manager_id: Optional[UUID] = None
    notes: Optional[str] = None


class EmployeeResponse(EmployeeBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    department_name: Optional[str] = None
    manager_name: Optional[str] = None

    model_config = {"from_attributes": True}


class EmployeeListResponse(BaseModel):
    """Employee list response with masked sensitive fields."""
    id: UUID
    full_name: str
    position: str
    department_name: Optional[str] = None
    personal_number: str  # masked: only last 4 digits
    status: str
    contract_type: str
    hire_date: date
    termination_date: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[UUID] = None
    manager_id: Optional[UUID] = None
    manager_name: Optional[str] = None
    base_salary: Optional[Decimal] = None
    salary_currency: Optional[str] = "GEL"
    created_at: datetime

    model_config = {"from_attributes": True}


class EmployeeDetailResponse(EmployeeBase):
    """Full employee detail — requires admin/accountant role."""
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    department_name: Optional[str] = None
    manager_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Employee Self-Service Profile ──────────────────────────────────────────────

class EmployeeSelfServiceUpdate(BaseModel):
    """Fields an employee can update on their own profile."""
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_name: Optional[str] = None


class EmployeeSelfServiceResponse(BaseModel):
    """Profile data visible to the employee themselves."""
    id: UUID
    full_name: str
    position: str
    department_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_name: Optional[str] = None
    contract_type: str
    status: str
    hire_date: date
    base_salary: Decimal
    salary_currency: str
    manager_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Employee Document Management ────────────────────────────────────────────────

class EmployeeDocumentBase(BaseModel):
    employee_id: UUID
    document_type: str = Field(..., max_length=30)
    document_number: Optional[str] = Field(None, max_length=100)
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_authority: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None


class EmployeeDocumentCreate(EmployeeDocumentBase):
    pass


class EmployeeDocumentUpdate(BaseModel):
    document_number: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_authority: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class EmployeeDocumentResponse(EmployeeDocumentBase):
    id: UUID
    company_id: UUID
    is_verified: bool = False
    verified_by: Optional[UUID] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    employee_name: Optional[str] = None

    model_config = {"from_attributes": True}


class EmployeeDocumentVerifyRequest(BaseModel):
    is_verified: bool = True
    notes: Optional[str] = None


# ── Leave Type ─────────────────────────────────────────────────────────────────

class LeaveTypeBase(BaseModel):
    code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    days_per_year: int = 0
    is_paid: bool = True
    requires_approval: bool = True
    carry_forward: bool = False
    max_consecutive_days: Optional[int] = None
    min_notice_days: Optional[int] = None
    is_active: bool = True


class LeaveTypeCreate(LeaveTypeBase):
    pass


class LeaveTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    days_per_year: Optional[int] = None
    is_paid: Optional[bool] = None
    requires_approval: Optional[bool] = None
    carry_forward: Optional[bool] = None
    max_consecutive_days: Optional[int] = None
    min_notice_days: Optional[int] = None
    is_active: Optional[bool] = None


class LeaveTypeResponse(LeaveTypeBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Leave Balance ──────────────────────────────────────────────────────────────

class LeaveBalanceBase(BaseModel):
    employee_id: UUID
    leave_type_id: UUID
    year: int = Field(..., ge=2020, le=2100)
    total_days: int = 0
    used_days: int = 0
    pending_days: int = 0
    remaining_days: int = 0
    carried_forward: int = 0


class LeaveBalanceCreate(LeaveBalanceBase):
    pass


class LeaveBalanceUpdate(BaseModel):
    total_days: Optional[int] = None
    used_days: Optional[int] = None
    pending_days: Optional[int] = None
    remaining_days: Optional[int] = None
    carried_forward: Optional[int] = None


class LeaveBalanceResponse(LeaveBalanceBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    employee_name: Optional[str] = None
    leave_type_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Leave Request ──────────────────────────────────────────────────────────────

class LeaveRequestBase(BaseModel):
    employee_id: UUID
    leave_type_id: UUID
    start_date: date
    end_date: date
    total_days: int = Field(..., ge=1)
    reason: Optional[str] = None
    notes: Optional[str] = None


class LeaveRequestCreate(LeaveRequestBase):
    pass


class LeaveRequestUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_days: Optional[int] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


class LeaveRequestApprove(BaseModel):
    approved: bool = True
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None


class LeaveRequestResponse(LeaveRequestBase):
    id: UUID
    company_id: UUID
    status: str
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    employee_name: Optional[str] = None
    leave_type_name: Optional[str] = None
    leave_type_code: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Attendance ─────────────────────────────────────────────────────────────────

class AttendanceBase(BaseModel):
    employee_id: UUID
    date: date
    clock_in: Optional[datetime] = None
    clock_out: Optional[datetime] = None
    status: str = "present"
    hours_worked: Optional[Decimal] = None
    overtime_hours: Optional[Decimal] = None
    late_minutes: Optional[int] = None
    early_departure_minutes: Optional[int] = None
    notes: Optional[str] = None


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(BaseModel):
    clock_in: Optional[datetime] = None
    clock_out: Optional[datetime] = None
    status: Optional[str] = None
    hours_worked: Optional[Decimal] = None
    overtime_hours: Optional[Decimal] = None
    late_minutes: Optional[int] = None
    early_departure_minutes: Optional[int] = None
    notes: Optional[str] = None


class AttendanceResponse(AttendanceBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    employee_name: Optional[str] = None

    model_config = {"from_attributes": True}


class AttendanceBulkCreate(BaseModel):
    """Bulk create attendance records for multiple employees on the same date."""
    date: date
    records: list[AttendanceCreate]


# ── Performance Review ────────────────────────────────────────────────────────

class PerformanceGoalBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    target_date: Optional[date] = None
    status: str = "not_started"
    progress_percent: int = 0
    notes: Optional[str] = None


class PerformanceGoalCreate(PerformanceGoalBase):
    pass


class PerformanceGoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_date: Optional[date] = None
    status: Optional[str] = None
    progress_percent: Optional[int] = None
    notes: Optional[str] = None


class PerformanceGoalResponse(PerformanceGoalBase):
    id: UUID
    company_id: UUID
    review_id: UUID
    employee_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PerformanceReviewBase(BaseModel):
    employee_id: UUID
    reviewer_id: Optional[UUID] = None
    review_period: str = Field(..., max_length=50)
    review_date: date
    due_date: Optional[date] = None
    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    productivity_rating: Optional[int] = Field(None, ge=1, le=5)
    quality_rating: Optional[int] = Field(None, ge=1, le=5)
    teamwork_rating: Optional[int] = Field(None, ge=1, le=5)
    communication_rating: Optional[int] = Field(None, ge=1, le=5)
    leadership_rating: Optional[int] = Field(None, ge=1, le=5)
    achievements: Optional[str] = None
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    goals_next_period: Optional[str] = None
    reviewer_comments: Optional[str] = None
    employee_comments: Optional[str] = None
    status: str = "draft"


class PerformanceReviewCreate(PerformanceReviewBase):
    goals: list[PerformanceGoalCreate] = []


class PerformanceReviewUpdate(BaseModel):
    reviewer_id: Optional[UUID] = None
    review_date: Optional[date] = None
    due_date: Optional[date] = None
    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    productivity_rating: Optional[int] = Field(None, ge=1, le=5)
    quality_rating: Optional[int] = Field(None, ge=1, le=5)
    teamwork_rating: Optional[int] = Field(None, ge=1, le=5)
    communication_rating: Optional[int] = Field(None, ge=1, le=5)
    leadership_rating: Optional[int] = Field(None, ge=1, le=5)
    achievements: Optional[str] = None
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    goals_next_period: Optional[str] = None
    reviewer_comments: Optional[str] = None
    employee_comments: Optional[str] = None
    status: Optional[str] = None


class PerformanceReviewResponse(PerformanceReviewBase):
    id: UUID
    company_id: UUID
    is_acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    employee_name: Optional[str] = None
    reviewer_name: Optional[str] = None
    goals: list[PerformanceGoalResponse] = []

    model_config = {"from_attributes": True}


class PerformanceReviewAcknowledge(BaseModel):
    employee_comments: Optional[str] = None


# ── Payroll Entry ───────────────────────────────────────────────────────────────

class PayrollEntryBase(BaseModel):
    employee_id: UUID
    period_year: int = Field(..., ge=2020, le=2100)
    period_month: int = Field(..., ge=1, le=12)
    base_salary: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    gross_pay: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    additions: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    deductions: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    income_tax: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    net_pay: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    status: str = "draft"
    payment_date: Optional[date] = None
    notes: Optional[str] = None


class PayrollEntryCreate(PayrollEntryBase):
    pass


class PayrollEntryUpdate(BaseModel):
    gross_pay: Optional[Decimal] = None
    additions: Optional[Decimal] = None
    deductions: Optional[Decimal] = None
    income_tax: Optional[Decimal] = None
    net_pay: Optional[Decimal] = None
    status: Optional[str] = None
    payment_date: Optional[date] = None
    notes: Optional[str] = None


class PayrollEntryResponse(PayrollEntryBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    employee_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Timesheet ───────────────────────────────────────────────────────────────────

class TimesheetBase(BaseModel):
    employee_id: UUID
    work_date: date
    hours_worked: Decimal = Field(default=Decimal("8"), max_digits=5, decimal_places=2)
    overtime_hours: Decimal = Field(default=Decimal("0"), max_digits=5, decimal_places=2)
    description: Optional[str] = None


class TimesheetCreate(TimesheetBase):
    pass


class TimesheetUpdate(BaseModel):
    hours_worked: Optional[Decimal] = None
    overtime_hours: Optional[Decimal] = None
    description: Optional[str] = None


class TimesheetResponse(TimesheetBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    employee_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Payroll Calculate Request ────────────────────────────────────────────────────

class PayrollCalculateRequest(BaseModel):
    """Calculate payroll for all active employees for a given period."""
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)

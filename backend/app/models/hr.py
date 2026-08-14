"""HR / Payroll models: Employee, Department, Payroll, Timesheet, Documents, Leave, Attendance, Performance."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, Boolean, UniqueConstraint, func, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Department(Base):
    """Company departments / divisions with hierarchy support."""
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_department_company_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    head_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    parent = relationship("Department", remote_side="Department.id", back_populates="children")
    children = relationship("Department", back_populates="parent", cascade="all, delete-orphan")
    employees = relationship("Employee", back_populates="department", foreign_keys="Employee.department_id")


class Employee(Base):
    """Employee registry with self-service profile fields."""
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("company_id", "personal_number", name="uq_employee_personal_number"),
    )

    class ContractType:
        PERMANENT = "permanent"
        FIXED_TERM = "fixed_term"
        CONTRACT = "contract"
        PROBATION = "probation"
        INTERN = "intern"
        CHOICES = [PERMANENT, FIXED_TERM, CONTRACT, PROBATION, INTERN]

    class Status:
        ACTIVE = "active"
        ON_LEAVE = "on_leave"
        TERMINATED = "terminated"
        RESIGNED = "resigned"
        SUSPENDED = "suspended"
        CHOICES = [ACTIVE, ON_LEAVE, TERMINATED, RESIGNED, SUSPENDED]

    class Gender:
        MALE = "male"
        FEMALE = "female"
        OTHER = "other"
        CHOICES = [MALE, FEMALE, OTHER]

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Identity
    personal_number: Mapped[str] = mapped_column(String(11), nullable=False)  # Georgian personal number
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Personal info (self-service)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Employment
    contract_type: Mapped[str] = mapped_column(String(20), default=ContractType.PERMANENT, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=Status.ACTIVE, nullable=False, index=True)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    probation_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Compensation
    base_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    salary_currency: Mapped[str] = mapped_column(String(3), default="GEL", nullable=False)
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Manager
    manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    department = relationship("Department", back_populates="employees", foreign_keys="Employee.department_id")
    payroll_entries = relationship("PayrollEntry", back_populates="employee", cascade="all, delete-orphan")
    timesheets = relationship("Timesheet", back_populates="employee", cascade="all, delete-orphan")
    documents = relationship("EmployeeDocument", back_populates="employee", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan")
    attendance_records = relationship("Attendance", back_populates="employee", cascade="all, delete-orphan")
    performance_reviews = relationship("PerformanceReview", back_populates="employee", cascade="all, delete-orphan")


class PayrollEntry(Base):
    """Monthly payroll calculation per employee."""
    __tablename__ = "payroll_entries"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_id", "period_year", "period_month", name="uq_payroll_period"),
    )

    class Status:
        DRAFT = "draft"
        APPROVED = "approved"
        PAID = "paid"
        CANCELLED = "cancelled"
        CHOICES = [DRAFT, APPROVED, PAID, CANCELLED]

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    period_year: Mapped[int] = mapped_column(nullable=False)
    period_month: Mapped[int] = mapped_column(nullable=False)

    base_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    gross_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    additions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    pension_contribution: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    income_tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    net_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default=Status.DRAFT, nullable=False)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("Employee", back_populates="payroll_entries")


class Payslip(Base):
    """Monthly payslip generated from a payroll entry."""
    __tablename__ = "payslips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    payroll_entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payroll_entries.id"), nullable=False, index=True)
    payslip_number: Mapped[str] = mapped_column(String(50), nullable=False)
    period_year: Mapped[int] = mapped_column(nullable=False)
    period_month: Mapped[int] = mapped_column(nullable=False)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    gross_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    additions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    pension_contribution: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    income_tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    net_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    employee = relationship("Employee")
    payroll_entry = relationship("PayrollEntry")


class Timesheet(Base):
    """Daily time tracking for employees."""
    __tablename__ = "timesheets"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", name="uq_timesheet_employee_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours_worked: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("8"), nullable=False)
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    employee = relationship("Employee", back_populates="timesheets")


# ── Employee Document Management ──────────────────────────────────────────────

class EmployeeDocument(Base):
    """Employee documents: contracts, IDs, certificates, etc."""
    __tablename__ = "employee_documents"
    __table_args__ = (
        UniqueConstraint("employee_id", "document_type", "document_number", name="uq_emp_doc_type_number"),
    )

    class DocumentType:
        CONTRACT = "contract"
        ID_CARD = "id_card"
        PASSPORT = "passport"
        DIPLOMA = "diploma"
        CERTIFICATE = "certificate"
        MEDICAL = "medical"
        TAX = "tax"
        OTHER = "other"
        CHOICES = [CONTRACT, ID_CARD, PASSPORT, DIPLOMA, CERTIFICATE, MEDICAL, TAX, OTHER]

    class Status:
        ACTIVE = "active"
        EXPIRED = "expired"
        PENDING = "pending"
        REJECTED = "rejected"
        CHOICES = [ACTIVE, EXPIRED, PENDING, REJECTED]

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)

    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # File reference
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Validity
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=Status.ACTIVE, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("Employee", back_populates="documents")


# ── Leave / Absence Tracking ──────────────────────────────────────────────────

class LeaveType(Base):
    """Types of leave (sick, vacation, maternity, etc.)."""
    __tablename__ = "leave_types"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_leave_type_company_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Allocation
    days_per_year: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    carry_forward: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_consecutive_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_notice_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    leave_requests = relationship("LeaveRequest", back_populates="leave_type")


class LeaveBalance(Base):
    """Annual leave balance per employee per leave type."""
    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type_id", "year", name="uq_leave_balance_emp_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    leave_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leave_types.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    total_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pending_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    remaining_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    carried_forward: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("Employee")
    leave_type = relationship("LeaveType")


class LeaveRequest(Base):
    """Employee leave/absence requests."""
    __tablename__ = "leave_requests"

    class Status:
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"
        CANCELLED = "cancelled"
        CHOICES = [PENDING, APPROVED, REJECTED, CANCELLED]

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    leave_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leave_types.id"), nullable=False)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_days: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=Status.PENDING, nullable=False, index=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("Employee", back_populates="leave_requests")
    leave_type = relationship("LeaveType", back_populates="leave_requests")


# ── Attendance Records ────────────────────────────────────────────────────────

class Attendance(Base):
    """Daily attendance records (clock-in/out)."""
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_attendance_employee_date"),
    )

    class Status:
        PRESENT = "present"
        ABSENT = "absent"
        LATE = "late"
        HALF_DAY = "half_day"
        HOLIDAY = "holiday"
        ON_LEAVE = "on_leave"
        CHOICES = [PRESENT, ABSENT, LATE, HALF_DAY, HOLIDAY, ON_LEAVE]

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)

    date: Mapped[date] = mapped_column(Date, nullable=False)
    clock_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    clock_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=Status.PRESENT, nullable=False)
    hours_worked: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    overtime_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    late_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    early_departure_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("Employee", back_populates="attendance_records")


# ── Performance Reviews ───────────────────────────────────────────────────────

class PerformanceReview(Base):
    """Employee performance reviews and evaluations."""
    __tablename__ = "performance_reviews"

    class Status:
        DRAFT = "draft"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        CANCELLED = "cancelled"
        CHOICES = [DRAFT, IN_PROGRESS, COMPLETED, CANCELLED]

    class Rating:
        EXCELLENT = 5
        GOOD = 4
        SATISFACTORY = 3
        NEEDS_IMPROVEMENT = 2
        POOR = 1
        CHOICES = [EXCELLENT, GOOD, SATISFACTORY, NEEDS_IMPROVEMENT, POOR]

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    review_period: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "2025-Q1", "2025-H1", "2025-Annual"
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Ratings (1-5)
    overall_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    productivity_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    teamwork_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    communication_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leadership_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Narrative
    achievements: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    areas_for_improvement: Mapped[str | None] = mapped_column(Text, nullable=True)
    goals_next_period: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    employee_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=Status.DRAFT, nullable=False)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("Employee", back_populates="performance_reviews")
    goals = relationship("PerformanceGoal", back_populates="review", cascade="all, delete-orphan")


class PerformanceGoal(Base):
    """Goals set during performance reviews."""
    __tablename__ = "performance_goals"

    class Status:
        NOT_STARTED = "not_started"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        ON_TRACK = "on_track"
        AT_RISK = "at_risk"
        CHOICES = [NOT_STARTED, IN_PROGRESS, COMPLETED, ON_TRACK, AT_RISK]

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("performance_reviews.id"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=Status.NOT_STARTED, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    review = relationship("PerformanceReview", back_populates="goals")

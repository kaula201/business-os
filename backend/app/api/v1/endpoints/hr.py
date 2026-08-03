"""HR / Payroll API: departments, employees, payroll, timesheets."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.hr import Department, Employee, PayrollEntry, Timesheet
from app.schemas.common import ResponseBase, PaginatedResponse
from app.schemas.hr import (
    DepartmentCreate, DepartmentResponse, DepartmentUpdate,
    EmployeeCreate, EmployeeListResponse, EmployeeResponse, EmployeeUpdate,
    PayrollEntryCreate, PayrollEntryResponse, PayrollEntryUpdate,
    PayrollCalculateRequest,
    TimesheetCreate, TimesheetResponse, TimesheetUpdate,
)

router = APIRouter(prefix="/hr", tags=["HR / ადამიანური რესურსები"])


# ── Departments ──────────────────────────────────────────────────────────────────

@router.get("/departments", response_model=ResponseBase[list[DepartmentResponse]])
async def list_departments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    result = await db.execute(
        select(Department)
        .where(Department.company_id == current_user.company_id, Department.is_active == True)
        .order_by(Department.code)
    )
    return ResponseBase(data=[DepartmentResponse.model_validate(d) for d in result.scalars().all()])


@router.post("/departments", response_model=ResponseBase[DepartmentResponse], status_code=201)
async def create_department(
    data: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_create")),
):
    existing = await db.execute(
        select(Department).where(
            Department.company_id == current_user.company_id,
            Department.code == data.code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="დეპარტამენტის კოდი უკვე არსებობს")

    dept = Department(company_id=current_user.company_id, **data.model_dump())
    db.add(dept)
    await db.flush()
    await db.refresh(dept)
    return ResponseBase(data=DepartmentResponse.model_validate(dept))


@router.patch("/departments/{dept_id}", response_model=ResponseBase[DepartmentResponse])
async def update_department(
    dept_id: UUID,
    data: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(Department).where(Department.id == dept_id, Department.company_id == current_user.company_id)
    )
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="დეპარტამენტი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dept, field, value)
    await db.flush()
    await db.refresh(dept)
    return ResponseBase(data=DepartmentResponse.model_validate(dept))


# ── Employees ────────────────────────────────────────────────────────────────────

@router.get("/employees", response_model=ResponseBase[PaginatedResponse[EmployeeListResponse]])
async def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    department_id: UUID | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    query = select(Employee).where(Employee.company_id == current_user.company_id)
    if status:
        query = query.where(Employee.status == status)
    if department_id:
        query = query.where(Employee.department_id == department_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            Employee.full_name.ilike(term) | Employee.personal_number.ilike(term) | Employee.position.ilike(term)
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.options(joinedload(Employee.department)).order_by(Employee.full_name)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    employees = result.unique().scalars().all()

    items = []
    for emp in employees:
        # Mask personal number — show only last 4 digits
        masked_pn = emp.personal_number
        if len(masked_pn) > 4:
            masked_pn = "*" * (len(masked_pn) - 4) + masked_pn[-4:]
        resp = EmployeeListResponse(
            id=emp.id, full_name=emp.full_name, position=emp.position,
            department_name=emp.department.name if emp.department else None,
            personal_number=masked_pn,
            status=emp.status, contract_type=emp.contract_type,
            hire_date=emp.hire_date, termination_date=emp.termination_date,
            email=emp.email, phone=emp.phone, created_at=emp.created_at,
        )
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/employees", response_model=ResponseBase[EmployeeResponse], status_code=201)
async def create_employee(
    data: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_create")),
):
    existing = await db.execute(
        select(Employee).where(
            Employee.company_id == current_user.company_id,
            Employee.personal_number == data.personal_number,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="პირადი ნომრით თანამშრომელი უკვე რეგისტრირებულია")

    emp = Employee(company_id=current_user.company_id, **data.model_dump())
    db.add(emp)
    await db.flush()
    await db.refresh(emp)

    # Load department name
    if emp.department_id:
        dept_result = await db.execute(select(Department).where(Department.id == emp.department_id))
        dept = dept_result.scalar_one_or_none()

    resp = EmployeeResponse.model_validate(emp)
    resp.department_name = dept.name if emp.department_id and dept else None
    return ResponseBase(data=resp)


@router.get("/employees/{emp_id}", response_model=ResponseBase[EmployeeResponse | EmployeeListResponse])
async def get_employee(
    emp_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    result = await db.execute(
        select(Employee)
        .where(Employee.id == emp_id, Employee.company_id == current_user.company_id)
        .options(joinedload(Employee.department))
    )
    emp = result.unique().scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    # Role-based masking: admin/accountant see full data, others see masked
    is_privileged = current_user.role in {User.Role.ADMIN, User.Role.ACCOUNTANT}
    if is_privileged:
        resp = EmployeeResponse.model_validate(emp)
        resp.department_name = emp.department.name if emp.department else None
    else:
        masked_pn = emp.personal_number
        if len(masked_pn) > 4:
            masked_pn = "*" * (len(masked_pn) - 4) + masked_pn[-4:]
        resp = EmployeeListResponse(
            id=emp.id, full_name=emp.full_name, position=emp.position,
            department_name=emp.department.name if emp.department else None,
            personal_number=masked_pn,
            status=emp.status, contract_type=emp.contract_type,
            hire_date=emp.hire_date, termination_date=emp.termination_date,
            email=emp.email, phone=emp.phone, created_at=emp.created_at,
        )
    return ResponseBase(data=resp)


@router.patch("/employees/{emp_id}", response_model=ResponseBase[EmployeeResponse])
async def update_employee(
    emp_id: UUID,
    data: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(Employee).where(Employee.id == emp_id, Employee.company_id == current_user.company_id)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(emp, field, value)
    await db.flush()
    await db.refresh(emp)

    if emp.department_id:
        dept_result = await db.execute(select(Department).where(Department.id == emp.department_id))
        dept = dept_result.scalar_one_or_none()

    resp = EmployeeResponse.model_validate(emp)
    resp.department_name = dept.name if emp.department_id and dept else None
    return ResponseBase(data=resp)


# ── Payroll ──────────────────────────────────────────────────────────────────────

@router.post("/payroll/calculate", response_model=ResponseBase[list[PayrollEntryResponse]])
async def calculate_payroll(
    data: PayrollCalculateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_create")),
):
    """Calculate payroll for all active employees for a given period."""
    emp_result = await db.execute(
        select(Employee).where(
            Employee.company_id == current_user.company_id,
            Employee.status == Employee.Status.ACTIVE,
        )
    )
    employees = emp_result.scalars().all()

    entries = []
    for emp in employees:
        # Check if entry already exists
        existing = await db.execute(
            select(PayrollEntry).where(
                PayrollEntry.company_id == current_user.company_id,
                PayrollEntry.employee_id == emp.id,
                PayrollEntry.period_year == data.year,
                PayrollEntry.period_month == data.month,
            )
        )
        if existing.scalar_one_or_none():
            continue

        gross_pay = emp.base_salary
        income_tax = (gross_pay * Decimal("0.15")).quantize(Decimal("0.01"))
        net_pay = (gross_pay - income_tax).quantize(Decimal("0.01"))

        entry = PayrollEntry(
            company_id=current_user.company_id,
            employee_id=emp.id,
            period_year=data.year,
            period_month=data.month,
            base_salary=emp.base_salary,
            gross_pay=gross_pay,
            additions=Decimal("0"),
            deductions=Decimal("0"),
            income_tax=income_tax,
            net_pay=net_pay,
        )
        db.add(entry)
        entries.append(entry)

    await db.flush()

    # Load employee names
    result = []
    for entry in entries:
        resp = PayrollEntryResponse.model_validate(entry)
        resp.employee_name = next((e.full_name for e in employees if e.id == entry.employee_id), None)
        result.append(resp)

    return ResponseBase(data=result)


@router.get("/payroll", response_model=ResponseBase[PaginatedResponse[PayrollEntryResponse]])
async def list_payroll(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    year: int | None = None,
    month: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    query = select(PayrollEntry).where(PayrollEntry.company_id == current_user.company_id)
    if year:
        query = query.where(PayrollEntry.period_year == year)
    if month:
        query = query.where(PayrollEntry.period_month == month)
    if status:
        query = query.where(PayrollEntry.status == status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.options(joinedload(PayrollEntry.employee)).order_by(
        PayrollEntry.period_year.desc(), PayrollEntry.period_month.desc(), PayrollEntry.employee_id
    )
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    entries = result.unique().scalars().all()

    items = []
    for entry in entries:
        resp = PayrollEntryResponse.model_validate(entry)
        resp.employee_name = entry.employee.full_name if entry.employee else None
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.patch("/payroll/{entry_id}", response_model=ResponseBase[PayrollEntryResponse])
async def update_payroll_entry(
    entry_id: UUID,
    data: PayrollEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(PayrollEntry)
        .where(PayrollEntry.id == entry_id, PayrollEntry.company_id == current_user.company_id)
        .options(joinedload(PayrollEntry.employee))
    )
    entry = result.unique().scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="სახელფასო ჩანაწერი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entry, field, value)
    await db.flush()
    await db.refresh(entry)

    resp = PayrollEntryResponse.model_validate(entry)
    resp.employee_name = entry.employee.full_name if entry.employee else None
    return ResponseBase(data=resp)


# ── Timesheets ──────────────────────────────────────────────────────────────────

@router.get("/timesheets", response_model=ResponseBase[PaginatedResponse[TimesheetResponse]])
async def list_timesheets(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    employee_id: UUID | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    query = select(Timesheet).where(Timesheet.company_id == current_user.company_id)
    if employee_id:
        query = query.where(Timesheet.employee_id == employee_id)
    if date_from:
        query = query.where(Timesheet.work_date >= date.fromisoformat(date_from))
    if date_to:
        query = query.where(Timesheet.work_date <= date.fromisoformat(date_to))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.options(joinedload(Timesheet.employee)).order_by(Timesheet.work_date.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    timesheets = result.unique().scalars().all()

    items = []
    for ts in timesheets:
        resp = TimesheetResponse.model_validate(ts)
        resp.employee_name = ts.employee.full_name if ts.employee else None
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/timesheets", response_model=ResponseBase[TimesheetResponse], status_code=201)
async def create_timesheet(
    data: TimesheetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_create")),
):
    # Verify employee belongs to company
    emp_result = await db.execute(
        select(Employee).where(
            Employee.id == data.employee_id,
            Employee.company_id == current_user.company_id,
        )
    )
    if not emp_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    # Check for duplicate date
    existing = await db.execute(
        select(Timesheet).where(
            Timesheet.employee_id == data.employee_id,
            Timesheet.work_date == data.work_date,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="ამ თარიღისთვის ჩანაწერი უკვე არსებობს")

    ts = Timesheet(company_id=current_user.company_id, **data.model_dump())
    db.add(ts)
    await db.flush()
    await db.refresh(ts)

    resp = TimesheetResponse.model_validate(ts)
    resp.employee_name = emp_result.scalar_one().full_name
    return ResponseBase(data=resp)

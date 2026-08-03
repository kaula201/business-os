"""HR enhanced: analytics, attendance, contracts, export, documents, leave, performance, self-service."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.hr import (
    Department, Employee, PayrollEntry, Timesheet,
    EmployeeDocument, LeaveType, LeaveBalance, LeaveRequest,
    Attendance, PerformanceReview, PerformanceGoal,
)
from app.schemas.common import ResponseBase, PaginatedResponse
from app.schemas.hr import (
    # Department
    DepartmentCreate, DepartmentResponse, DepartmentUpdate, DepartmentTreeNode,
    # Employee
    EmployeeCreate, EmployeeListResponse, EmployeeResponse, EmployeeUpdate,
    EmployeeSelfServiceUpdate, EmployeeSelfServiceResponse,
    # Documents
    EmployeeDocumentCreate, EmployeeDocumentResponse, EmployeeDocumentUpdate,
    EmployeeDocumentVerifyRequest,
    # Leave
    LeaveTypeCreate, LeaveTypeResponse, LeaveTypeUpdate,
    LeaveBalanceCreate, LeaveBalanceResponse, LeaveBalanceUpdate,
    LeaveRequestCreate, LeaveRequestResponse, LeaveRequestApprove,
    # Attendance
    AttendanceCreate, AttendanceResponse, AttendanceUpdate, AttendanceBulkCreate,
    # Performance
    PerformanceReviewCreate, PerformanceReviewResponse, PerformanceReviewUpdate,
    PerformanceReviewAcknowledge,
    PerformanceGoalCreate, PerformanceGoalResponse, PerformanceGoalUpdate,
    # Payroll
    PayrollEntryCreate, PayrollEntryResponse, PayrollEntryUpdate,
    PayrollCalculateRequest,
    # Timesheet
    TimesheetCreate, TimesheetResponse, TimesheetUpdate,
)
from pydantic import BaseModel
from io import BytesIO
import openpyxl
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/hr", tags=["HR — გაძლიერებული"])


# ── Analytics ──────────────────────────────────────────────────────────────────

class HRAnalytics(BaseModel):
    total_employees: int
    active_employees: int
    on_leave_employees: int
    departments: int
    total_monthly_payroll: Decimal
    avg_salary: Decimal
    new_hires_this_month: int
    timesheets_this_month: int
    pending_leave_requests: int
    pending_reviews: int
    expired_documents: int


@router.get("/analytics", response_model=ResponseBase[HRAnalytics])
async def hr_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    company_id = current_user.company_id
    today = date.today()
    month_start = today.replace(day=1)

    total = (await db.execute(select(func.count(Employee.id)).where(Employee.company_id == company_id))).scalar()
    active = (await db.execute(select(func.count(Employee.id)).where(Employee.company_id == company_id, Employee.status == Employee.Status.ACTIVE))).scalar()
    on_leave = (await db.execute(select(func.count(Employee.id)).where(Employee.company_id == company_id, Employee.status == Employee.Status.ON_LEAVE))).scalar()
    dept_count = (await db.execute(select(func.count(Department.id)).where(Department.company_id == company_id, Department.is_active == True))).scalar()

    salary_rows = (await db.execute(
        select(func.coalesce(func.sum(Employee.base_salary), 0))
        .where(Employee.company_id == company_id, Employee.status == Employee.Status.ACTIVE)
    )).scalar()

    avg_salary = (await db.execute(
        select(func.avg(Employee.base_salary))
        .where(Employee.company_id == company_id, Employee.status == Employee.Status.ACTIVE)
    )).scalar()

    new_hires = (await db.execute(
        select(func.count(Employee.id))
        .where(Employee.company_id == company_id, Employee.hire_date >= month_start)
    )).scalar()

    ts_count = (await db.execute(
        select(func.count(Timesheet.id))
        .where(Timesheet.company_id == company_id, Timesheet.work_date >= month_start)
    )).scalar()

    pending_leaves = (await db.execute(
        select(func.count(LeaveRequest.id))
        .where(LeaveRequest.company_id == company_id, LeaveRequest.status == LeaveRequest.Status.PENDING)
    )).scalar()

    pending_reviews = (await db.execute(
        select(func.count(PerformanceReview.id))
        .where(PerformanceReview.company_id == company_id, PerformanceReview.status.in_(["draft", "in_progress"]))
    )).scalar()

    expired_docs = (await db.execute(
        select(func.count(EmployeeDocument.id))
        .where(
            EmployeeDocument.company_id == company_id,
            EmployeeDocument.expiry_date.isnot(None),
            EmployeeDocument.expiry_date < today,
            EmployeeDocument.status == EmployeeDocument.Status.ACTIVE,
        )
    )).scalar()

    return ResponseBase(data=HRAnalytics(
        total_employees=total or 0, active_employees=active or 0,
        on_leave_employees=on_leave or 0,
        departments=dept_count or 0,
        total_monthly_payroll=Decimal(str(salary_rows or 0)),
        avg_salary=Decimal(str(avg_salary or 0)).quantize(Decimal("0.01")),
        new_hires_this_month=new_hires or 0,
        timesheets_this_month=ts_count or 0,
        pending_leave_requests=pending_leaves or 0,
        pending_reviews=pending_reviews or 0,
        expired_documents=expired_docs or 0,
    ))


# ── Department Hierarchy ──────────────────────────────────────────────────────

async def _build_dept_tree(dept: Department, db: AsyncSession) -> dict:
    """Recursively build department tree node."""
    children_result = await db.execute(
        select(Department)
        .where(Department.parent_id == dept.id, Department.is_active == True)
        .order_by(Department.code)
    )
    children = children_result.scalars().all()
    return {
        "id": dept.id,
        "code": dept.code,
        "name": dept.name,
        "parent_id": dept.parent_id,
        "manager_id": dept.manager_id,
        "description": dept.description,
        "head_count": dept.head_count,
        "is_active": dept.is_active,
        "children": [await _build_dept_tree(c, db) for c in children],
    }


@router.get("/department-tree", response_model=ResponseBase[list[DepartmentTreeNode]])
async def department_tree(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    """Get full department hierarchy tree."""
    root_result = await db.execute(
        select(Department)
        .where(
            Department.company_id == current_user.company_id,
            Department.parent_id.is_(None),
            Department.is_active == True,
        )
        .order_by(Department.code)
    )
    roots = root_result.scalars().all()
    tree = [await _build_dept_tree(r, db) for r in roots]
    return ResponseBase(data=tree)


@router.get("/departments/{dept_id}/children", response_model=ResponseBase[list[DepartmentResponse]])
async def department_children(
    dept_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    """Get direct children of a department."""
    result = await db.execute(
        select(Department)
        .where(Department.parent_id == dept_id, Department.company_id == current_user.company_id)
        .order_by(Department.code)
    )
    depts = result.scalars().all()
    items = []
    for d in depts:
        resp = DepartmentResponse.model_validate(d)
        children_count = await db.execute(
            select(func.count(Department.id)).where(Department.parent_id == d.id)
        )
        resp.children_count = children_count.scalar() or 0
        items.append(resp)
    return ResponseBase(data=items)


# ── Enhanced Department CRUD ──────────────────────────────────────────────────

@router.get("/departments/{dept_id}", response_model=ResponseBase[DepartmentResponse])
async def get_department(
    dept_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    result = await db.execute(
        select(Department).where(Department.id == dept_id, Department.company_id == current_user.company_id)
    )
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="დეპარტამენტი არ მოიძებნა")
    resp = DepartmentResponse.model_validate(dept)
    children_count = await db.execute(
        select(func.count(Department.id)).where(Department.parent_id == dept.id)
    )
    resp.children_count = children_count.scalar() or 0
    return ResponseBase(data=resp)


# ── Employee Self-Service ──────────────────────────────────────────────────────

@router.get("/me", response_model=ResponseBase[EmployeeSelfServiceResponse])
async def my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    """Get own employee profile (self-service)."""
    result = await db.execute(
        select(Employee)
        .where(Employee.user_id == current_user.id, Employee.company_id == current_user.company_id)
        .options(joinedload(Employee.department))
    )
    emp = result.unique().scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="თანამშრომლის პროფილი არ მოიძებნა")

    manager_name = None
    if emp.manager_id:
        mgr_result = await db.execute(select(Employee.full_name).where(Employee.id == emp.manager_id))
        manager_name = mgr_result.scalar_one_or_none()

    return ResponseBase(data=EmployeeSelfServiceResponse(
        id=emp.id, full_name=emp.full_name, position=emp.position,
        department_name=emp.department.name if emp.department else None,
        email=emp.email, phone=emp.phone, address=emp.address,
        gender=emp.gender, birth_date=emp.birth_date,
        emergency_contact_name=emp.emergency_contact_name,
        emergency_contact_phone=emp.emergency_contact_phone,
        bank_account_number=emp.bank_account_number,
        bank_name=emp.bank_name,
        contract_type=emp.contract_type, status=emp.status,
        hire_date=emp.hire_date,
        base_salary=emp.base_salary, salary_currency=emp.salary_currency,
        manager_name=manager_name,
        created_at=emp.created_at,
    ))


@router.patch("/me", response_model=ResponseBase[EmployeeSelfServiceResponse])
async def update_my_profile(
    data: EmployeeSelfServiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    """Update own employee profile (self-service)."""
    result = await db.execute(
        select(Employee)
        .where(Employee.user_id == current_user.id, Employee.company_id == current_user.company_id)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="თანამშრომლის პროფილი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(emp, field, value)
    await db.flush()
    await db.refresh(emp)

    manager_name = None
    if emp.manager_id:
        mgr_result = await db.execute(select(Employee.full_name).where(Employee.id == emp.manager_id))
        manager_name = mgr_result.scalar_one_or_none()

    return ResponseBase(data=EmployeeSelfServiceResponse(
        id=emp.id, full_name=emp.full_name, position=emp.position,
        department_name=emp.department.name if emp.department else None,
        email=emp.email, phone=emp.phone, address=emp.address,
        gender=emp.gender, birth_date=emp.birth_date,
        emergency_contact_name=emp.emergency_contact_name,
        emergency_contact_phone=emp.emergency_contact_phone,
        bank_account_number=emp.bank_account_number,
        bank_name=emp.bank_name,
        contract_type=emp.contract_type, status=emp.status,
        hire_date=emp.hire_date,
        base_salary=emp.base_salary, salary_currency=emp.salary_currency,
        manager_name=manager_name,
        created_at=emp.created_at,
    ))


@router.get("/me/leave-balances", response_model=ResponseBase[list[LeaveBalanceResponse]])
async def my_leave_balances(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    """Get own leave balances."""
    result = await db.execute(
        select(Employee.id).where(Employee.user_id == current_user.id, Employee.company_id == current_user.company_id)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    balances = await db.execute(
        select(LeaveBalance)
        .where(LeaveBalance.employee_id == emp, LeaveBalance.company_id == current_user.company_id)
        .options(joinedload(LeaveBalance.leave_type))
        .order_by(LeaveBalance.year.desc())
    )
    items = []
    for b in balances.unique().scalars().all():
        resp = LeaveBalanceResponse.model_validate(b)
        resp.employee_name = None
        resp.leave_type_name = b.leave_type.name if b.leave_type else None
        items.append(resp)
    return ResponseBase(data=items)


@router.get("/me/leave-requests", response_model=ResponseBase[list[LeaveRequestResponse]])
async def my_leave_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    """Get own leave requests."""
    result = await db.execute(
        select(Employee.id).where(Employee.user_id == current_user.id, Employee.company_id == current_user.company_id)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    requests = await db.execute(
        select(LeaveRequest)
        .where(LeaveRequest.employee_id == emp, LeaveRequest.company_id == current_user.company_id)
        .options(joinedload(LeaveRequest.leave_type))
        .order_by(LeaveRequest.created_at.desc())
    )
    items = []
    for lr in requests.unique().scalars().all():
        resp = LeaveRequestResponse.model_validate(lr)
        resp.employee_name = None
        resp.leave_type_name = lr.leave_type.name if lr.leave_type else None
        resp.leave_type_code = lr.leave_type.code if lr.leave_type else None
        items.append(resp)
    return ResponseBase(data=items)


@router.get("/me/documents", response_model=ResponseBase[list[EmployeeDocumentResponse]])
async def my_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    """Get own documents."""
    result = await db.execute(
        select(Employee.id).where(Employee.user_id == current_user.id, Employee.company_id == current_user.company_id)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    docs = await db.execute(
        select(EmployeeDocument)
        .where(EmployeeDocument.employee_id == emp, EmployeeDocument.company_id == current_user.company_id)
        .order_by(EmployeeDocument.created_at.desc())
    )
    items = [EmployeeDocumentResponse.model_validate(d) for d in docs.scalars().all()]
    return ResponseBase(data=items)


@router.get("/me/performance-reviews", response_model=ResponseBase[list[PerformanceReviewResponse]])
async def my_performance_reviews(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    """Get own performance reviews."""
    result = await db.execute(
        select(Employee.id).where(Employee.user_id == current_user.id, Employee.company_id == current_user.company_id)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    reviews = await db.execute(
        select(PerformanceReview)
        .where(PerformanceReview.employee_id == emp, PerformanceReview.company_id == current_user.company_id)
        .options(joinedload(PerformanceReview.goals))
        .order_by(PerformanceReview.review_date.desc())
    )
    items = []
    for r in reviews.unique().scalars().all():
        resp = PerformanceReviewResponse.model_validate(r)
        resp.employee_name = None
        resp.reviewer_name = None
        resp.goals = [PerformanceGoalResponse.model_validate(g) for g in r.goals]
        items.append(resp)
    return ResponseBase(data=items)


# ── Employee Document Management ──────────────────────────────────────────────

@router.get("/documents", response_model=ResponseBase[PaginatedResponse[EmployeeDocumentResponse]])
async def list_employee_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    employee_id: UUID | None = None,
    document_type: str | None = None,
    status: str | None = None,
    expired: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    query = select(EmployeeDocument).where(EmployeeDocument.company_id == current_user.company_id)
    if employee_id:
        query = query.where(EmployeeDocument.employee_id == employee_id)
    if document_type:
        query = query.where(EmployeeDocument.document_type == document_type)
    if status:
        query = query.where(EmployeeDocument.status == status)
    if expired is True:
        query = query.where(
            EmployeeDocument.expiry_date.isnot(None),
            EmployeeDocument.expiry_date < date.today(),
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.options(joinedload(EmployeeDocument.employee)).order_by(EmployeeDocument.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    docs = result.unique().scalars().all()

    items = []
    for d in docs:
        resp = EmployeeDocumentResponse.model_validate(d)
        resp.employee_name = d.employee.full_name if d.employee else None
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/documents", response_model=ResponseBase[EmployeeDocumentResponse], status_code=201)
async def create_employee_document(
    data: EmployeeDocumentCreate,
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
    emp = emp_result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    doc = EmployeeDocument(company_id=current_user.company_id, **data.model_dump())
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    resp = EmployeeDocumentResponse.model_validate(doc)
    resp.employee_name = emp.full_name
    return ResponseBase(data=resp)


@router.get("/documents/{doc_id}", response_model=ResponseBase[EmployeeDocumentResponse])
async def get_employee_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    result = await db.execute(
        select(EmployeeDocument)
        .where(EmployeeDocument.id == doc_id, EmployeeDocument.company_id == current_user.company_id)
        .options(joinedload(EmployeeDocument.employee))
    )
    doc = result.unique().scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")
    resp = EmployeeDocumentResponse.model_validate(doc)
    resp.employee_name = doc.employee.full_name if doc.employee else None
    return ResponseBase(data=resp)


@router.patch("/documents/{doc_id}", response_model=ResponseBase[EmployeeDocumentResponse])
async def update_employee_document(
    doc_id: UUID,
    data: EmployeeDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(EmployeeDocument)
        .where(EmployeeDocument.id == doc_id, EmployeeDocument.company_id == current_user.company_id)
        .options(joinedload(EmployeeDocument.employee))
    )
    doc = result.unique().scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(doc, field, value)
    await db.flush()
    await db.refresh(doc)

    resp = EmployeeDocumentResponse.model_validate(doc)
    resp.employee_name = doc.employee.full_name if doc.employee else None
    return ResponseBase(data=resp)


@router.post("/documents/{doc_id}/verify", response_model=ResponseBase[EmployeeDocumentResponse])
async def verify_employee_document(
    doc_id: UUID,
    data: EmployeeDocumentVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(EmployeeDocument)
        .where(EmployeeDocument.id == doc_id, EmployeeDocument.company_id == current_user.company_id)
        .options(joinedload(EmployeeDocument.employee))
    )
    doc = result.unique().scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    doc.is_verified = data.is_verified
    doc.verified_by = current_user.id
    doc.verified_at = datetime.utcnow()
    if data.notes is not None:
        doc.notes = data.notes
    await db.flush()
    await db.refresh(doc)

    resp = EmployeeDocumentResponse.model_validate(doc)
    resp.employee_name = doc.employee.full_name if doc.employee else None
    return ResponseBase(data=resp)


# ── Leave Types ───────────────────────────────────────────────────────────────

@router.get("/leave-types", response_model=ResponseBase[list[LeaveTypeResponse]])
async def list_leave_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    result = await db.execute(
        select(LeaveType)
        .where(LeaveType.company_id == current_user.company_id, LeaveType.is_active == True)
        .order_by(LeaveType.code)
    )
    return ResponseBase(data=[LeaveTypeResponse.model_validate(lt) for lt in result.scalars().all()])


@router.post("/leave-types", response_model=ResponseBase[LeaveTypeResponse], status_code=201)
async def create_leave_type(
    data: LeaveTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_create")),
):
    existing = await db.execute(
        select(LeaveType).where(
            LeaveType.company_id == current_user.company_id,
            LeaveType.code == data.code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="შვებულების ტიპის კოდი უკვე არსებობს")

    lt = LeaveType(company_id=current_user.company_id, **data.model_dump())
    db.add(lt)
    await db.flush()
    await db.refresh(lt)
    return ResponseBase(data=LeaveTypeResponse.model_validate(lt))


@router.patch("/leave-types/{lt_id}", response_model=ResponseBase[LeaveTypeResponse])
async def update_leave_type(
    lt_id: UUID,
    data: LeaveTypeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(LeaveType).where(LeaveType.id == lt_id, LeaveType.company_id == current_user.company_id)
    )
    lt = result.scalar_one_or_none()
    if not lt:
        raise HTTPException(status_code=404, detail="შვებულების ტიპი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lt, field, value)
    await db.flush()
    await db.refresh(lt)
    return ResponseBase(data=LeaveTypeResponse.model_validate(lt))


# ── Leave Balances ────────────────────────────────────────────────────────────

@router.get("/leave-balances", response_model=ResponseBase[list[LeaveBalanceResponse]])
async def list_leave_balances(
    employee_id: UUID | None = None,
    year: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    query = select(LeaveBalance).where(LeaveBalance.company_id == current_user.company_id)
    if employee_id:
        query = query.where(LeaveBalance.employee_id == employee_id)
    if year:
        query = query.where(LeaveBalance.year == year)

    query = query.options(
        joinedload(LeaveBalance.employee),
        joinedload(LeaveBalance.leave_type),
    ).order_by(LeaveBalance.year.desc(), LeaveBalance.employee_id)

    result = await db.execute(query)
    items = []
    for b in result.unique().scalars().all():
        resp = LeaveBalanceResponse.model_validate(b)
        resp.employee_name = b.employee.full_name if b.employee else None
        resp.leave_type_name = b.leave_type.name if b.leave_type else None
        items.append(resp)
    return ResponseBase(data=items)


@router.post("/leave-balances", response_model=ResponseBase[LeaveBalanceResponse], status_code=201)
async def create_leave_balance(
    data: LeaveBalanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_create")),
):
    # Verify employee
    emp_result = await db.execute(
        select(Employee).where(Employee.id == data.employee_id, Employee.company_id == current_user.company_id)
    )
    if not emp_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    # Verify leave type
    lt_result = await db.execute(
        select(LeaveType).where(LeaveType.id == data.leave_type_id, LeaveType.company_id == current_user.company_id)
    )
    if not lt_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="შვებულების ტიპი არ მოიძებნა")

    # Check for existing balance
    existing = await db.execute(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == data.employee_id,
            LeaveBalance.leave_type_id == data.leave_type_id,
            LeaveBalance.year == data.year,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="ნაშთი უკვე არსებობს ამ პერიოდისთვის")

    lb = LeaveBalance(company_id=current_user.company_id, **data.model_dump())
    db.add(lb)
    await db.flush()
    await db.refresh(lb)
    return ResponseBase(data=LeaveBalanceResponse.model_validate(lb))


@router.patch("/leave-balances/{lb_id}", response_model=ResponseBase[LeaveBalanceResponse])
async def update_leave_balance(
    lb_id: UUID,
    data: LeaveBalanceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(LeaveBalance)
        .where(LeaveBalance.id == lb_id, LeaveBalance.company_id == current_user.company_id)
        .options(joinedload(LeaveBalance.employee), joinedload(LeaveBalance.leave_type))
    )
    lb = result.unique().scalar_one_or_none()
    if not lb:
        raise HTTPException(status_code=404, detail="ნაშთი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lb, field, value)
    await db.flush()
    await db.refresh(lb)

    resp = LeaveBalanceResponse.model_validate(lb)
    resp.employee_name = lb.employee.full_name if lb.employee else None
    resp.leave_type_name = lb.leave_type.name if lb.leave_type else None
    return ResponseBase(data=resp)


# ── Leave Requests ───────────────────────────────────────────────────────────

@router.get("/leave-requests", response_model=ResponseBase[PaginatedResponse[LeaveRequestResponse]])
async def list_leave_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    employee_id: UUID | None = None,
    status: str | None = None,
    leave_type_id: UUID | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    query = select(LeaveRequest).where(LeaveRequest.company_id == current_user.company_id)
    if employee_id:
        query = query.where(LeaveRequest.employee_id == employee_id)
    if status:
        query = query.where(LeaveRequest.status == status)
    if leave_type_id:
        query = query.where(LeaveRequest.leave_type_id == leave_type_id)
    if date_from:
        query = query.where(LeaveRequest.start_date >= date.fromisoformat(date_from))
    if date_to:
        query = query.where(LeaveRequest.end_date <= date.fromisoformat(date_to))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.options(
        joinedload(LeaveRequest.employee),
        joinedload(LeaveRequest.leave_type),
    ).order_by(LeaveRequest.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    requests = result.unique().scalars().all()

    items = []
    for lr in requests:
        resp = LeaveRequestResponse.model_validate(lr)
        resp.employee_name = lr.employee.full_name if lr.employee else None
        resp.leave_type_name = lr.leave_type.name if lr.leave_type else None
        resp.leave_type_code = lr.leave_type.code if lr.leave_type else None
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/leave-requests", response_model=ResponseBase[LeaveRequestResponse], status_code=201)
async def create_leave_request(
    data: LeaveRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_create")),
):
    # Verify employee
    emp_result = await db.execute(
        select(Employee).where(
            Employee.id == data.employee_id,
            Employee.company_id == current_user.company_id,
        )
    )
    emp = emp_result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    # Verify leave type
    lt_result = await db.execute(
        select(LeaveType).where(
            LeaveType.id == data.leave_type_id,
            LeaveType.company_id == current_user.company_id,
        )
    )
    lt = lt_result.scalar_one_or_none()
    if not lt:
        raise HTTPException(status_code=404, detail="შვებულების ტიპი არ მოიძებნა")

    # Check for overlapping leave
    overlap = await db.execute(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == data.employee_id,
            LeaveRequest.status.in_([LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED]),
            LeaveRequest.start_date <= data.end_date,
            LeaveRequest.end_date >= data.start_date,
        )
    )
    if overlap.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="ამ პერიოდში უკვე არსებობს შვებულების მოთხოვნა")

    lr = LeaveRequest(company_id=current_user.company_id, **data.model_dump())
    db.add(lr)
    await db.flush()
    await db.refresh(lr)

    resp = LeaveRequestResponse.model_validate(lr)
    resp.employee_name = emp.full_name
    resp.leave_type_name = lt.name
    resp.leave_type_code = lt.code
    return ResponseBase(data=resp)


@router.get("/leave-requests/{lr_id}", response_model=ResponseBase[LeaveRequestResponse])
async def get_leave_request(
    lr_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    result = await db.execute(
        select(LeaveRequest)
        .where(LeaveRequest.id == lr_id, LeaveRequest.company_id == current_user.company_id)
        .options(joinedload(LeaveRequest.employee), joinedload(LeaveRequest.leave_type))
    )
    lr = result.unique().scalar_one_or_none()
    if not lr:
        raise HTTPException(status_code=404, detail="შვებულების მოთხოვნა არ მოიძებნა")

    resp = LeaveRequestResponse.model_validate(lr)
    resp.employee_name = lr.employee.full_name if lr.employee else None
    resp.leave_type_name = lr.leave_type.name if lr.leave_type else None
    resp.leave_type_code = lr.leave_type.code if lr.leave_type else None
    return ResponseBase(data=resp)


@router.post("/leave-requests/{lr_id}/approve", response_model=ResponseBase[LeaveRequestResponse])
async def approve_leave_request(
    lr_id: UUID,
    data: LeaveRequestApprove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(LeaveRequest)
        .where(LeaveRequest.id == lr_id, LeaveRequest.company_id == current_user.company_id)
        .options(joinedload(LeaveRequest.employee), joinedload(LeaveRequest.leave_type))
    )
    lr = result.unique().scalar_one_or_none()
    if not lr:
        raise HTTPException(status_code=404, detail="შვებულების მოთხოვნა არ მოიძებნა")

    if lr.status != LeaveRequest.Status.PENDING:
        raise HTTPException(status_code=400, detail="მოთხოვნა უკვე დამუშავებულია")

    if data.approved:
        lr.status = LeaveRequest.Status.APPROVED
        lr.approved_by = current_user.id
        lr.approved_at = datetime.utcnow()

        # Update leave balance
        balance_result = await db.execute(
            select(LeaveBalance).where(
                LeaveBalance.employee_id == lr.employee_id,
                LeaveBalance.leave_type_id == lr.leave_type_id,
                LeaveBalance.year == lr.start_date.year,
            )
        )
        balance = balance_result.scalar_one_or_none()
        if balance:
            balance.used_days = (balance.used_days or 0) + lr.total_days
            balance.pending_days = max(0, (balance.pending_days or 0) - lr.total_days)
            balance.remaining_days = max(0, balance.total_days - balance.used_days)
    else:
        lr.status = LeaveRequest.Status.REJECTED
        lr.rejection_reason = data.rejection_reason

        # Release pending days
        balance_result = await db.execute(
            select(LeaveBalance).where(
                LeaveBalance.employee_id == lr.employee_id,
                LeaveBalance.leave_type_id == lr.leave_type_id,
                LeaveBalance.year == lr.start_date.year,
            )
        )
        balance = balance_result.scalar_one_or_none()
        if balance:
            balance.pending_days = max(0, (balance.pending_days or 0) - lr.total_days)
            balance.remaining_days = balance.total_days - balance.used_days - balance.pending_days

    await db.flush()
    await db.refresh(lr)

    resp = LeaveRequestResponse.model_validate(lr)
    resp.employee_name = lr.employee.full_name if lr.employee else None
    resp.leave_type_name = lr.leave_type.name if lr.leave_type else None
    resp.leave_type_code = lr.leave_type.code if lr.leave_type else None
    return ResponseBase(data=resp)


@router.post("/leave-requests/{lr_id}/cancel", response_model=ResponseBase[LeaveRequestResponse])
async def cancel_leave_request(
    lr_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(LeaveRequest)
        .where(LeaveRequest.id == lr_id, LeaveRequest.company_id == current_user.company_id)
        .options(joinedload(LeaveRequest.employee), joinedload(LeaveRequest.leave_type))
    )
    lr = result.unique().scalar_one_or_none()
    if not lr:
        raise HTTPException(status_code=404, detail="შვებულების მოთხოვნა არ მოიძებნა")

    if lr.status == LeaveRequest.Status.CANCELLED:
        raise HTTPException(status_code=400, detail="მოთხოვნა უკვე გაუქმებულია")

    old_status = lr.status
    lr.status = LeaveRequest.Status.CANCELLED

    # Release balance adjustments
    balance_result = await db.execute(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == lr.employee_id,
            LeaveBalance.leave_type_id == lr.leave_type_id,
            LeaveBalance.year == lr.start_date.year,
        )
    )
    balance = balance_result.scalar_one_or_none()
    if balance:
        if old_status == LeaveRequest.Status.APPROVED:
            balance.used_days = max(0, (balance.used_days or 0) - lr.total_days)
        elif old_status == LeaveRequest.Status.PENDING:
            balance.pending_days = max(0, (balance.pending_days or 0) - lr.total_days)
        balance.remaining_days = balance.total_days - balance.used_days - balance.pending_days

    await db.flush()
    await db.refresh(lr)

    resp = LeaveRequestResponse.model_validate(lr)
    resp.employee_name = lr.employee.full_name if lr.employee else None
    resp.leave_type_name = lr.leave_type.name if lr.leave_type else None
    resp.leave_type_code = lr.leave_type.code if lr.leave_type else None
    return ResponseBase(data=resp)


# ── Attendance Records ────────────────────────────────────────────────────────

@router.get("/attendance-records", response_model=ResponseBase[PaginatedResponse[AttendanceResponse]])
async def list_attendance_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    employee_id: UUID | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    query = select(Attendance).where(Attendance.company_id == current_user.company_id)
    if employee_id:
        query = query.where(Attendance.employee_id == employee_id)
    if date_from:
        query = query.where(Attendance.date >= date.fromisoformat(date_from))
    if date_to:
        query = query.where(Attendance.date <= date.fromisoformat(date_to))
    if status:
        query = query.where(Attendance.status == status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.options(joinedload(Attendance.employee)).order_by(Attendance.date.desc(), Attendance.employee_id)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    records = result.unique().scalars().all()

    items = []
    for a in records:
        resp = AttendanceResponse.model_validate(a)
        resp.employee_name = a.employee.full_name if a.employee else None
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/attendance-records", response_model=ResponseBase[AttendanceResponse], status_code=201)
async def create_attendance_record(
    data: AttendanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_create")),
):
    # Verify employee
    emp_result = await db.execute(
        select(Employee).where(
            Employee.id == data.employee_id,
            Employee.company_id == current_user.company_id,
        )
    )
    if not emp_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    # Check for duplicate
    existing = await db.execute(
        select(Attendance).where(
            Attendance.employee_id == data.employee_id,
            Attendance.date == data.date,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="ამ თარიღისთვის ჩანაწერი უკვე არსებობს")

    att = Attendance(company_id=current_user.company_id, **data.model_dump())
    db.add(att)
    await db.flush()
    await db.refresh(att)

    resp = AttendanceResponse.model_validate(att)
    resp.employee_name = emp_result.scalar_one().full_name
    return ResponseBase(data=resp)


@router.post("/attendance-records/bulk", response_model=ResponseBase[list[AttendanceResponse]], status_code=201)
async def bulk_create_attendance(
    data: AttendanceBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_create")),
):
    """Bulk create attendance records for multiple employees on the same date."""
    results = []
    for record in data.records:
        # Verify employee
        emp_result = await db.execute(
            select(Employee).where(
                Employee.id == record.employee_id,
                Employee.company_id == current_user.company_id,
            )
        )
        emp = emp_result.scalar_one_or_none()
        if not emp:
            continue  # Skip invalid employees

        # Check for duplicate
        existing = await db.execute(
            select(Attendance).where(
                Attendance.employee_id == record.employee_id,
                Attendance.date == record.date,
            )
        )
        if existing.scalar_one_or_none():
            continue

        att = Attendance(company_id=current_user.company_id, **record.model_dump())
        db.add(att)
        await db.flush()
        await db.refresh(att)

        resp = AttendanceResponse.model_validate(att)
        resp.employee_name = emp.full_name
        results.append(resp)

    return ResponseBase(data=results)


@router.patch("/attendance-records/{att_id}", response_model=ResponseBase[AttendanceResponse])
async def update_attendance_record(
    att_id: UUID,
    data: AttendanceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(Attendance)
        .where(Attendance.id == att_id, Attendance.company_id == current_user.company_id)
        .options(joinedload(Attendance.employee))
    )
    att = result.unique().scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="დასწრების ჩანაწერი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(att, field, value)
    await db.flush()
    await db.refresh(att)

    resp = AttendanceResponse.model_validate(att)
    resp.employee_name = att.employee.full_name if att.employee else None
    return ResponseBase(data=resp)


# ── Attendance Summary ─────────────────────────────────────────────────────────

class EmployeeAttendance(BaseModel):
    employee_id: UUID
    employee_name: str
    department_name: str | None
    total_hours: float
    total_days: int
    avg_hours_per_day: float
    present_days: int
    absent_days: int
    late_days: int


@router.get("/attendance", response_model=ResponseBase[list[EmployeeAttendance]])
async def attendance_summary(
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    company_id = current_user.company_id
    today = date.today()
    d_from = date.fromisoformat(date_from) if date_from else today.replace(day=1)
    d_to = date.fromisoformat(date_to) if date_to else today

    rows = (await db.execute(
        select(
            Employee.id, Employee.full_name, Department.name,
            func.coalesce(func.sum(Attendance.hours_worked), 0),
            func.count(Attendance.id),
        )
        .outerjoin(Attendance, Attendance.employee_id == Employee.id)
        .outerjoin(Department, Department.id == Employee.department_id)
        .where(
            Employee.company_id == company_id,
            Employee.status == Employee.Status.ACTIVE,
            Attendance.date.between(d_from, d_to),
        )
        .group_by(Employee.id, Employee.full_name, Department.name)
        .order_by(Employee.full_name)
    )).all()

    # Count statuses per employee
    items = []
    for eid, name, dept, hours, days in rows:
        days_count = days or 0

        # Get status breakdown
        status_counts = (await db.execute(
            select(Attendance.status, func.count(Attendance.id))
            .where(
                Attendance.employee_id == eid,
                Attendance.date.between(d_from, d_to),
            )
            .group_by(Attendance.status)
        )).all()
        status_map = {s: c for s, c in status_counts}

        items.append(EmployeeAttendance(
            employee_id=eid, employee_name=name, department_name=dept,
            total_hours=float(hours), total_days=days_count,
            avg_hours_per_day=float(hours) / days_count if days_count > 0 else 0,
            present_days=status_map.get("present", 0),
            absent_days=status_map.get("absent", 0),
            late_days=status_map.get("late", 0),
        ))

    return ResponseBase(data=items)


# ── Performance Reviews ──────────────────────────────────────────────────────

@router.get("/performance-reviews", response_model=ResponseBase[PaginatedResponse[PerformanceReviewResponse]])
async def list_performance_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    employee_id: UUID | None = None,
    status: str | None = None,
    review_period: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    query = select(PerformanceReview).where(PerformanceReview.company_id == current_user.company_id)
    if employee_id:
        query = query.where(PerformanceReview.employee_id == employee_id)
    if status:
        query = query.where(PerformanceReview.status == status)
    if review_period:
        query = query.where(PerformanceReview.review_period == review_period)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.options(
        joinedload(PerformanceReview.employee),
        joinedload(PerformanceReview.goals),
    ).order_by(PerformanceReview.review_date.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    reviews = result.unique().scalars().all()

    items = []
    for r in reviews:
        resp = PerformanceReviewResponse.model_validate(r)
        resp.employee_name = r.employee.full_name if r.employee else None
        resp.reviewer_name = None
        if r.reviewer_id:
            reviewer = await db.execute(select(Employee.full_name).where(Employee.id == r.reviewer_id))
            resp.reviewer_name = reviewer.scalar_one_or_none()
        resp.goals = [PerformanceGoalResponse.model_validate(g) for g in r.goals]
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/performance-reviews", response_model=ResponseBase[PerformanceReviewResponse], status_code=201)
async def create_performance_review(
    data: PerformanceReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_create")),
):
    # Verify employee
    emp_result = await db.execute(
        select(Employee).where(
            Employee.id == data.employee_id,
            Employee.company_id == current_user.company_id,
        )
    )
    emp = emp_result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    review = PerformanceReview(
        company_id=current_user.company_id,
        **data.model_dump(exclude={"goals"}),
    )
    db.add(review)
    await db.flush()

    # Create goals
    goals = []
    for g in data.goals:
        goal = PerformanceGoal(
            company_id=current_user.company_id,
            review_id=review.id,
            employee_id=data.employee_id,
            **g.model_dump(),
        )
        db.add(goal)
        goals.append(goal)

    await db.flush()
    await db.refresh(review)

    resp = PerformanceReviewResponse.model_validate(review)
    resp.employee_name = emp.full_name
    resp.reviewer_name = None
    if review.reviewer_id:
        reviewer = await db.execute(select(Employee.full_name).where(Employee.id == review.reviewer_id))
        resp.reviewer_name = reviewer.scalar_one_or_none()
    resp.goals = [PerformanceGoalResponse.model_validate(g) for g in goals]
    return ResponseBase(data=resp)


@router.get("/performance-reviews/{pr_id}", response_model=ResponseBase[PerformanceReviewResponse])
async def get_performance_review(
    pr_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    result = await db.execute(
        select(PerformanceReview)
        .where(PerformanceReview.id == pr_id, PerformanceReview.company_id == current_user.company_id)
        .options(joinedload(PerformanceReview.employee), joinedload(PerformanceReview.goals))
    )
    review = result.unique().scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="შეფასება არ მოიძებნა")

    resp = PerformanceReviewResponse.model_validate(review)
    resp.employee_name = review.employee.full_name if review.employee else None
    resp.reviewer_name = None
    if review.reviewer_id:
        reviewer = await db.execute(select(Employee.full_name).where(Employee.id == review.reviewer_id))
        resp.reviewer_name = reviewer.scalar_one_or_none()
    resp.goals = [PerformanceGoalResponse.model_validate(g) for g in review.goals]
    return ResponseBase(data=resp)


@router.patch("/performance-reviews/{pr_id}", response_model=ResponseBase[PerformanceReviewResponse])
async def update_performance_review(
    pr_id: UUID,
    data: PerformanceReviewUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(PerformanceReview)
        .where(PerformanceReview.id == pr_id, PerformanceReview.company_id == current_user.company_id)
        .options(joinedload(PerformanceReview.employee), joinedload(PerformanceReview.goals))
    )
    review = result.unique().scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="შეფასება არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(review, field, value)
    await db.flush()
    await db.refresh(review)

    resp = PerformanceReviewResponse.model_validate(review)
    resp.employee_name = review.employee.full_name if review.employee else None
    resp.reviewer_name = None
    if review.reviewer_id:
        reviewer = await db.execute(select(Employee.full_name).where(Employee.id == review.reviewer_id))
        resp.reviewer_name = reviewer.scalar_one_or_none()
    resp.goals = [PerformanceGoalResponse.model_validate(g) for g in review.goals]
    return ResponseBase(data=resp)


@router.post("/performance-reviews/{pr_id}/acknowledge", response_model=ResponseBase[PerformanceReviewResponse])
async def acknowledge_performance_review(
    pr_id: UUID,
    data: PerformanceReviewAcknowledge,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    result = await db.execute(
        select(PerformanceReview)
        .where(PerformanceReview.id == pr_id, PerformanceReview.company_id == current_user.company_id)
        .options(joinedload(PerformanceReview.employee), joinedload(PerformanceReview.goals))
    )
    review = result.unique().scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="შეფასება არ მოიძებნა")

    review.is_acknowledged = True
    review.acknowledged_at = datetime.utcnow()
    if data.employee_comments is not None:
        review.employee_comments = data.employee_comments
    await db.flush()
    await db.refresh(review)

    resp = PerformanceReviewResponse.model_validate(review)
    resp.employee_name = review.employee.full_name if review.employee else None
    resp.reviewer_name = None
    if review.reviewer_id:
        reviewer = await db.execute(select(Employee.full_name).where(Employee.id == review.reviewer_id))
        resp.reviewer_name = reviewer.scalar_one_or_none()
    resp.goals = [PerformanceGoalResponse.model_validate(g) for g in review.goals]
    return ResponseBase(data=resp)


# ── Performance Goals ──────────────────────────────────────────────────────────

@router.get("/performance-goals", response_model=ResponseBase[list[PerformanceGoalResponse]])
async def list_performance_goals(
    employee_id: UUID | None = None,
    review_id: UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    query = select(PerformanceGoal).where(PerformanceGoal.company_id == current_user.company_id)
    if employee_id:
        query = query.where(PerformanceGoal.employee_id == employee_id)
    if review_id:
        query = query.where(PerformanceGoal.review_id == review_id)
    if status:
        query = query.where(PerformanceGoal.status == status)

    query = query.order_by(PerformanceGoal.created_at.desc())
    result = await db.execute(query)
    return ResponseBase(data=[PerformanceGoalResponse.model_validate(g) for g in result.scalars().all()])


@router.patch("/performance-goals/{goal_id}", response_model=ResponseBase[PerformanceGoalResponse])
async def update_performance_goal(
    goal_id: UUID,
    data: PerformanceGoalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_edit")),
):
    result = await db.execute(
        select(PerformanceGoal).where(
            PerformanceGoal.id == goal_id,
            PerformanceGoal.company_id == current_user.company_id,
        )
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="მიზანი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(goal, field, value)
    await db.flush()
    await db.refresh(goal)
    return ResponseBase(data=PerformanceGoalResponse.model_validate(goal))


# ── Payroll Summary ────────────────────────────────────────────────────────────

class PayrollSummary(BaseModel):
    period: str
    total_gross: Decimal
    total_tax: Decimal
    total_net: Decimal
    employee_count: int


@router.get("/payroll-summary", response_model=ResponseBase[list[PayrollSummary]])
async def payroll_summary(
    year: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    company_id = current_user.company_id
    y = year or date.today().year

    rows = (await db.execute(
        select(
            PayrollEntry.period_year, PayrollEntry.period_month,
            func.count(PayrollEntry.id),
            func.coalesce(func.sum(PayrollEntry.gross_pay), 0),
            func.coalesce(func.sum(PayrollEntry.income_tax), 0),
            func.coalesce(func.sum(PayrollEntry.net_pay), 0),
        )
        .where(PayrollEntry.company_id == company_id, PayrollEntry.period_year == y)
        .group_by(PayrollEntry.period_year, PayrollEntry.period_month)
        .order_by(PayrollEntry.period_year.desc(), PayrollEntry.period_month.desc())
    )).all()

    months_ka = ["", "იანვარი", "თებერვალი", "მარტი", "აპრილი", "მაისი", "ივნისი",
                  "ივლისი", "აგვისტო", "სექტემბერი", "ოქტომბერი", "ნოემბერი", "დეკემბერი"]

    items = []
    for py, pm, cnt, gross, tax, net in rows:
        items.append(PayrollSummary(
            period=f"{months_ka[pm]} {py}",
            total_gross=Decimal(str(gross)), total_tax=Decimal(str(tax)),
            total_net=Decimal(str(net)), employee_count=cnt,
        ))

    return ResponseBase(data=items)


# ── Export ──────────────────────────────────────────────────────────────────────

@router.get("/export/employees")
async def export_employees(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    rows = (await db.execute(
        select(Employee)
        .where(Employee.company_id == current_user.company_id)
        .options(joinedload(Employee.department))
        .order_by(Employee.full_name)
    )).unique().scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "თანამშრომლები"
    ws.append(["სახელი", "პირადი ნომერი", "პოზიცია", "დეპარტამენტი", "სტატუსი",
               "ბაზური ხელფასი", "დაქირავების თარიღი", "ტელეფონი", "ელფოსტა",
               "სქესი", "დაბადების თარიღი", "კონტრაქტის ტიპი", "მენეჯერი"])
    for e in rows:
        manager_name = None
        if e.manager_id:
            mgr = await db.execute(select(Employee.full_name).where(Employee.id == e.manager_id))
            manager_name = mgr.scalar_one_or_none()
        ws.append([e.full_name, e.personal_number, e.position,
                   e.department.name if e.department else "", e.status,
                   float(e.base_salary), str(e.hire_date or ""), e.phone or "", e.email or "",
                   e.gender or "", str(e.birth_date or ""), e.contract_type, manager_name or ""])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=employees.xlsx"})


@router.get("/export/payroll")
async def export_payroll(
    year: int | None = None,
    month: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("hr", "can_access")),
):
    filters = [PayrollEntry.company_id == current_user.company_id]
    if year:
        filters.append(PayrollEntry.period_year == year)
    if month:
        filters.append(PayrollEntry.period_month == month)

    rows = (await db.execute(
        select(PayrollEntry)
        .where(*filters)
        .options(joinedload(PayrollEntry.employee))
        .order_by(PayrollEntry.period_year.desc(), PayrollEntry.period_month.desc())
    )).unique().scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "სახელფასო"
    ws.append(["თანამშრომელი", "პერიოდი", "ბაზური", "დარიცხული", "დამატებები",
               "დაკავებები", "საშემოსავლო", "გადასახდელი", "სტატუსი"])
    for e in rows:
        ws.append([e.employee.full_name if e.employee else "",
                   f"{e.period_month}/{e.period_year}",
                   float(e.base_salary), float(e.gross_pay), float(e.additions),
                   float(e.deductions), float(e.income_tax), float(e.net_pay), e.status])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=payroll.xlsx"})

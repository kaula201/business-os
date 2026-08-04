"""Expenses API: employee expense tracking, categories, approvals."""
import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.audit import AuditLog
from app.models.expenses import Expense, ExpenseCategory
from app.models.user import User
from app.schemas.common import ResponseBase, PaginatedResponse
from app.services.accounting_periods import ensure_period_open
from app.schemas.expenses import (
    ExpenseCategoryCreate,
    ExpenseCategoryResponse,
    ExpenseCreate,
    ExpenseResponse,
    ExpenseUpdate,
)

router = APIRouter(prefix="/expenses", tags=["ხარჯები"])


# ── Categories ────────────────────────────────────────────────────────

@router.get("/categories", response_model=ResponseBase[list[ExpenseCategoryResponse]])
async def list_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExpenseCategory)
        .where(ExpenseCategory.company_id == current_user.company_id)
        .order_by(ExpenseCategory.name)
    )
    return ResponseBase(data=result.scalars().all())


@router.post("/categories", response_model=ResponseBase[ExpenseCategoryResponse], status_code=201)
async def create_category(
    payload: ExpenseCategoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cat = ExpenseCategory(company_id=current_user.company_id, **payload.model_dump())
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return ResponseBase(data=cat, message="კატეგორია დამატებულია")


# ── Expenses ─────────────────────────────────────────────────────────

@router.get("/", response_model=ResponseBase[PaginatedResponse[ExpenseResponse]])
async def list_expenses(
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Expense)
        .options(
            joinedload(Expense.employee),
            joinedload(Expense.category),
        )
        .where(Expense.company_id == current_user.company_id)
    )
    if status:
        query = query.where(Expense.status == status)
    if search:
        query = query.where(
            Expense.description.ilike(f"%{search}%")
            | Expense.employee.has(User.full_name.ilike(f"%{search}%"))
        )
    query = query.order_by(Expense.expense_date.desc(), Expense.created_at.desc())

    total = (
        await db.execute(
            select(func.count()).select_from(query.subquery())
        )
    ).scalar() or 0
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    expenses = result.unique().scalars().all()

    data = []
    for e in expenses:
        data.append(ExpenseResponse(
            id=e.id,
            company_id=e.company_id,
            employee_id=e.employee_id,
            employee_name=e.employee.full_name if e.employee else "—",
            category_id=e.category_id,
            category_name=e.category.name if e.category else None,
            project_id=e.project_id,
            expense_date=e.expense_date,
            description=e.description,
            amount=float(e.amount),
            currency=e.currency,
            tax_type=e.tax_type,
            tax_amount=float(e.tax_amount) if e.tax_amount else None,
            status=e.status,
            receipt_url=e.receipt_url,
            notes=e.notes,
            approved_by=e.approved_by,
            approved_at=e.approved_at,
            created_at=e.created_at,
            updated_at=e.updated_at,
        ))
    return ResponseBase(data=PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=data,
    ))


@router.post("/", response_model=ResponseBase[ExpenseResponse], status_code=201)
async def create_expense(
    payload: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_period_open(db, current_user.company_id, payload.expense_date)
    if payload.category_id is not None:
        category_exists = await db.scalar(
            select(ExpenseCategory.id).where(
                ExpenseCategory.id == payload.category_id,
                ExpenseCategory.company_id == current_user.company_id,
                ExpenseCategory.is_active.is_(True),
            )
        )
        if not category_exists:
            raise HTTPException(status_code=404, detail="ხარჯის კატეგორია არ მოიძებნა")

    expense = Expense(
        company_id=current_user.company_id,
        employee_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(expense)
    await db.flush()

    db.add(AuditLog(
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="create",
        entity_type="expense",
        entity_id=expense.id,
        details=json.dumps({"amount": str(expense.amount), "description": expense.description}, ensure_ascii=False),
    ))

    # Re-fetch with joins
    result = await db.execute(
        select(Expense)
        .options(joinedload(Expense.employee), joinedload(Expense.category))
        .where(Expense.id == expense.id)
    )
    e = result.unique().scalar_one()

    return ResponseBase(data=ExpenseResponse(
        id=e.id, company_id=e.company_id, employee_id=e.employee_id,
        employee_name=e.employee.full_name if e.employee else "—",
        category_id=e.category_id, category_name=e.category.name if e.category else None,
        project_id=e.project_id,
        expense_date=e.expense_date, description=e.description, amount=float(e.amount),
        currency=e.currency, tax_type=e.tax_type, tax_amount=float(e.tax_amount) if e.tax_amount else None,
        status=e.status, receipt_url=e.receipt_url, notes=e.notes,
        approved_by=e.approved_by, approved_at=e.approved_at,
        created_at=e.created_at, updated_at=e.updated_at,
    ), message="ხარჯი დაფიქსირებულია")


@router.put("/{expense_id}", response_model=ResponseBase[ExpenseResponse])
async def update_expense(
    expense_id: UUID,
    payload: ExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    expense = (
        await db.execute(
            select(Expense).where(
                Expense.id == expense_id,
                Expense.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="ხარჯი არ მოიძებნა")

    await ensure_period_open(db, current_user.company_id, expense.expense_date)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="განახლების მონაცემები არ არის მოწოდებული")
    for key, value in update_data.items():
        setattr(expense, key, value)
    await db.flush()

    result = await db.execute(
        select(Expense)
        .options(joinedload(Expense.employee), joinedload(Expense.category))
        .where(Expense.id == expense.id)
    )
    e = result.unique().scalar_one()
    return ResponseBase(data=ExpenseResponse(
        id=e.id, company_id=e.company_id, employee_id=e.employee_id,
        employee_name=e.employee.full_name if e.employee else "—",
        category_id=e.category_id, category_name=e.category.name if e.category else None,
        project_id=e.project_id,
        expense_date=e.expense_date, description=e.description, amount=float(e.amount),
        currency=e.currency, tax_type=e.tax_type, tax_amount=float(e.tax_amount) if e.tax_amount else None,
        status=e.status, receipt_url=e.receipt_url, notes=e.notes,
        approved_by=e.approved_by, approved_at=e.approved_at,
        created_at=e.created_at, updated_at=e.updated_at,
    ), message="ხარჯი განახლებულია")


@router.post("/{expense_id}/approve", response_model=ResponseBase[ExpenseResponse])
async def approve_expense(
    expense_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in {User.Role.ADMIN, User.Role.MANAGER}:
        raise HTTPException(status_code=403, detail="ხარჯის დამტკიცების უფლება არ გაქვთ")

    expense = (
        await db.execute(
            select(Expense).where(
                Expense.id == expense_id,
                Expense.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="ხარჯი არ მოიძებნა")
    if expense.status != "pending":
        raise HTTPException(status_code=400, detail="მხოლოდ pending სტატუსის ხარჯის დამტკიცება შეიძლება")

    await ensure_period_open(db, current_user.company_id, expense.expense_date)

    expense.status = "approved"
    expense.approved_by = current_user.id
    expense.approved_at = utc_now()
    await db.flush()

    result = await db.execute(
        select(Expense)
        .options(joinedload(Expense.employee), joinedload(Expense.category))
        .where(Expense.id == expense.id)
    )
    e = result.unique().scalar_one()
    return ResponseBase(data=ExpenseResponse(
        id=e.id, company_id=e.company_id, employee_id=e.employee_id,
        employee_name=e.employee.full_name if e.employee else "—",
        category_id=e.category_id, category_name=e.category.name if e.category else None,
        project_id=e.project_id,
        expense_date=e.expense_date, description=e.description, amount=float(e.amount),
        currency=e.currency, tax_type=e.tax_type, tax_amount=float(e.tax_amount) if e.tax_amount else None,
        status=e.status, receipt_url=e.receipt_url, notes=e.notes,
        approved_by=e.approved_by, approved_at=e.approved_at,
        created_at=e.created_at, updated_at=e.updated_at,
    ), message="ხარჯი დამტკიცებულია")


@router.post("/{expense_id}/reject", response_model=ResponseBase[ExpenseResponse])
async def reject_expense(
    expense_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in {User.Role.ADMIN, User.Role.MANAGER}:
        raise HTTPException(status_code=403, detail="ხარჯის უარყოფის უფლება არ გაქვთ")

    expense = (
        await db.execute(
            select(Expense).where(
                Expense.id == expense_id,
                Expense.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="ხარჯი არ მოიძებნა")
    if expense.status != "pending":
        raise HTTPException(status_code=400, detail="მხოლოდ pending სტატუსის ხარჯის უარყოფა შეიძლება")

    await ensure_period_open(db, current_user.company_id, expense.expense_date)

    expense.status = "rejected"
    await db.flush()

    result = await db.execute(
        select(Expense)
        .options(joinedload(Expense.employee), joinedload(Expense.category))
        .where(Expense.id == expense.id)
    )
    e = result.unique().scalar_one()
    return ResponseBase(data=ExpenseResponse(
        id=e.id, company_id=e.company_id, employee_id=e.employee_id,
        employee_name=e.employee.full_name if e.employee else "—",
        category_id=e.category_id, category_name=e.category.name if e.category else None,
        project_id=e.project_id,
        expense_date=e.expense_date, description=e.description, amount=float(e.amount),
        currency=e.currency, tax_type=e.tax_type, tax_amount=float(e.tax_amount) if e.tax_amount else None,
        status=e.status, receipt_url=e.receipt_url, notes=e.notes,
        approved_by=e.approved_by, approved_at=e.approved_at,
        created_at=e.created_at, updated_at=e.updated_at,
    ), message="ხარჯი უარყოფილია")

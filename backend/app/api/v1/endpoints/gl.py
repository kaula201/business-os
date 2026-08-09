"""General Ledger API endpoints: Chart of Accounts, Journal Entries, automated posting."""
import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.purchase_orders import add_audit, allocate_document_number
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.gl import (
    GLAccountCreate,
    GLAccountResponse,
    GLAccountUpdate,
    JournalEntryCreate,
    JournalEntryListResponse,
    JournalEntryLineResponse,
    JournalEntryResponse,
)

router = APIRouter(prefix="/gl", tags=["მთავარი წიგნი"])


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def require_gl_role(user: User) -> None:
    if user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="მთავარ წიგნზე წვდომის უფლება არ გაქვთ")


# ── Chart of Accounts ──────────────────────────────────────────────────────


@router.get("/accounts/", response_model=ResponseBase[PaginatedResponse[GLAccountResponse]])
async def list_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    account_type: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    filters = [GLAccount.company_id == current_user.company_id]
    if account_type:
        filters.append(GLAccount.account_type == account_type)
    if is_active is not None:
        filters.append(GLAccount.is_active == is_active)
    if search:
        term = f"%{search.strip()}%"
        filters.append(GLAccount.code.ilike(term) | GLAccount.name.ilike(term))
    total = (await db.execute(select(func.count(GLAccount.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(GLAccount)
            .where(*filters)
            .order_by(GLAccount.code)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[GLAccountResponse(
            id=a.id, company_id=a.company_id, code=a.code, name=a.name,
            account_type=a.account_type, parent_id=a.parent_id,
            is_active=a.is_active, description=a.description,
            created_at=a.created_at, updated_at=a.updated_at,
        ) for a in rows],
    ))


@router.post("/accounts/", response_model=ResponseBase[GLAccountResponse])
async def create_account(
    data: GLAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    existing = (
        await db.execute(select(GLAccount.id).where(
            GLAccount.company_id == current_user.company_id,
            GLAccount.code == data.code.strip(),
        ).limit(1))
    ).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="ანგარიშის კოდი უკვე არსებობს")
    if data.parent_id:
        parent = (
            await db.execute(select(GLAccount).where(
                GLAccount.id == data.parent_id,
                GLAccount.company_id == current_user.company_id,
            ))
        ).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="მშობელი ანგარიში არ მოიძებნა")
    account = GLAccount(
        company_id=current_user.company_id,
        code=data.code.strip(),
        name=data.name.strip(),
        account_type=data.account_type.strip(),
        parent_id=data.parent_id,
        description=data.description.strip() if data.description else None,
    )
    db.add(account)
    await db.flush()
    add_audit(db, current_user, "gl_account.created", "gl_account", account.id, {
        "code": account.code, "name": account.name, "type": account.account_type,
    })
    await db.refresh(account)
    return ResponseBase(data=GLAccountResponse(
        id=account.id, company_id=account.company_id, code=account.code,
        name=account.name, account_type=account.account_type,
        parent_id=account.parent_id, is_active=account.is_active,
        description=account.description, created_at=account.created_at,
        updated_at=account.updated_at,
    ))


@router.get("/accounts/{account_id}", response_model=ResponseBase[GLAccountResponse])
async def get_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    account = (
        await db.execute(select(GLAccount).where(
            GLAccount.id == account_id,
            GLAccount.company_id == current_user.company_id,
        ))
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="ანგარიში არ მოიძებნა")
    return ResponseBase(data=GLAccountResponse(
        id=account.id, company_id=account.company_id, code=account.code,
        name=account.name, account_type=account.account_type,
        parent_id=account.parent_id, is_active=account.is_active,
        description=account.description, created_at=account.created_at,
        updated_at=account.updated_at,
    ))


@router.patch("/accounts/{account_id}", response_model=ResponseBase[GLAccountResponse])
async def update_account(
    account_id: UUID,
    data: GLAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    account = (
        await db.execute(select(GLAccount).where(
            GLAccount.id == account_id,
            GLAccount.company_id == current_user.company_id,
        ).with_for_update())
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="ანგარიში არ მოიძებნა")
    if data.name is not None:
        account.name = data.name.strip()
    if data.is_active is not None:
        account.is_active = data.is_active
    if data.description is not None:
        account.description = data.description.strip() if data.description else None
    await db.flush()
    add_audit(db, current_user, "gl_account.updated", "gl_account", account.id, {
        "name": account.name, "is_active": account.is_active,
    })
    await db.refresh(account)
    return ResponseBase(data=GLAccountResponse(
        id=account.id, company_id=account.company_id, code=account.code,
        name=account.name, account_type=account.account_type,
        parent_id=account.parent_id, is_active=account.is_active,
        description=account.description, created_at=account.created_at,
        updated_at=account.updated_at,
    ))


# ── Journal Entries ─────────────────────────────────────────────────────────


@router.get("/journal-entries/", response_model=ResponseBase[PaginatedResponse[JournalEntryListResponse]])
async def list_journal_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    reference_type: str | None = None,
    reference_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    filters = [JournalEntry.company_id == current_user.company_id]
    if reference_type:
        filters.append(JournalEntry.reference_type == reference_type)
    if reference_id:
        filters.append(JournalEntry.reference_id == reference_id)
    if date_from:
        filters.append(JournalEntry.entry_date >= date_from)
    if date_to:
        filters.append(JournalEntry.entry_date <= date_to)
    total = (await db.execute(select(func.count(JournalEntry.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(JournalEntry)
            .where(*filters)
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[JournalEntryListResponse(
            id=e.id, entry_number=e.entry_number, entry_date=e.entry_date,
            description=e.description, reference_type=e.reference_type,
            is_reversal=e.is_reversal, created_at=e.created_at,
        ) for e in rows],
    ))


@router.post("/journal-entries/", response_model=ResponseBase[JournalEntryResponse], status_code=201)
async def create_manual_journal_entry(
    data: JournalEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a manual journal entry (double-entry). Validates balance and tenant-scoped accounts."""
    require_gl_role(current_user)

    # ── Validate accounting period is open ────────────────────────────
    from app.services.accounting_periods import ensure_period_open
    try:
        await ensure_period_open(db, current_user.company_id, data.entry_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Validate accounts belong to company + are active ───────────────
    account_ids = [l.gl_account_id for l in data.lines]
    rows = (
        await db.execute(
            select(GLAccount).where(
                GLAccount.company_id == current_user.company_id,
                GLAccount.id.in_(account_ids),
                GLAccount.is_active == True,
            )
        )
    ).scalars().all()
    found = {a.id: a for a in rows}
    missing = [str(aid) for aid in account_ids if aid not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"ანგარიში ვერ მოიძებნა ან არააქტიურია: {', '.join(missing)}")

    # ── Balance validation: sum(debits) == sum(credits), each line one-sided ──
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    normalized_lines = []
    for i, line in enumerate(data.lines, start=1):
        dr = money(line.debit_amount)
        cr = money(line.credit_amount)
        if dr > 0 and cr > 0:
            raise HTTPException(status_code=400, detail=f"სტრიქონი {i}: debit და credit ერთდროულად არ შეიძლება")
        if dr == 0 and cr == 0:
            raise HTTPException(status_code=400, detail=f"სტრიქონი {i}: თანხა უნდა იყოს ნულისგან განსხვავებული")
        total_debit += dr
        total_credit += cr
        normalized_lines.append((i, dr, cr, line.gl_account_id, line.description))
    if total_debit != total_credit:
        raise HTTPException(
            status_code=400,
            detail=f"ბალანსი არ იყრის თავს: debit={total_debit}, credit={total_credit}",
        )

    # ── Generate entry number (JE-YYYYMMDD-NNN) ────────────────────────
    prefix = f"JE-{data.entry_date.strftime('%Y%m%d')}"
    same_day = (
        await db.execute(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.company_id == current_user.company_id,
                JournalEntry.entry_number.like(f"{prefix}-%"),
            )
        )
    ).scalar_one()
    entry_number = f"{prefix}-{same_day + 1:03d}"

    # ── Create entry + lines ───────────────────────────────────────────
    entry = JournalEntry(
        company_id=current_user.company_id,
        entry_number=entry_number,
        entry_date=data.entry_date,
        description=data.description,
        reference_type="manual",
        reference_id=uuid.uuid4(),
        created_by=current_user.id,
    )
    db.add(entry)
    await db.flush()
    for line_number, dr, cr, gl_account_id, desc in normalized_lines:
        db.add(JournalEntryLine(
            journal_entry_id=entry.id,
            gl_account_id=gl_account_id,
            line_number=line_number,
            debit_amount=dr,
            credit_amount=cr,
            description=desc,
        ))
    await db.commit()
    await db.refresh(entry)

    add_audit(db, current_user, "journal_entry.created", "journal_entry", entry.id, {
        "entry_number": entry_number,
        "entry_date": str(data.entry_date),
        "description": data.description,
    })
    await db.commit()

    result = (
        await db.execute(
            select(JournalEntry).options(selectinload(JournalEntry.lines)).where(JournalEntry.id == entry.id)
        )
    ).scalar_one()
    return ResponseBase(data=JournalEntryResponse(
        id=result.id, company_id=result.company_id, entry_number=result.entry_number,
        entry_date=result.entry_date, description=result.description,
        reference_type=result.reference_type, reference_id=result.reference_id,
        is_reversal=result.is_reversal, reversed_entry_id=result.reversed_entry_id,
        created_by=result.created_by, created_at=result.created_at,
        lines=[JournalEntryLineResponse(
            id=l.id, journal_entry_id=l.journal_entry_id, gl_account_id=l.gl_account_id,
            line_number=l.line_number, debit_amount=float(l.debit_amount),
            credit_amount=float(l.credit_amount), description=l.description,
            created_at=l.created_at,
        ) for l in result.lines],
    ))


@router.get("/journal-entries/{entry_id}", response_model=ResponseBase[JournalEntryResponse])
async def get_journal_entry(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    entry = (
        await db.execute(
            select(JournalEntry)
            .where(JournalEntry.id == entry_id, JournalEntry.company_id == current_user.company_id)
            .options(selectinload(JournalEntry.lines))
        )
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="საბუღალტრო ჩანაწერი არ მოიძებნა")
    return ResponseBase(data=JournalEntryResponse(
        id=entry.id, company_id=entry.company_id, entry_number=entry.entry_number,
        entry_date=entry.entry_date, description=entry.description,
        reference_type=entry.reference_type, reference_id=entry.reference_id,
        is_reversal=entry.is_reversal, reversed_entry_id=entry.reversed_entry_id,
        created_by=entry.created_by, created_at=entry.created_at,
        lines=[JournalEntryLineResponse(
            id=l.id, journal_entry_id=l.journal_entry_id,
            gl_account_id=l.gl_account_id, line_number=l.line_number,
            debit_amount=float(l.debit_amount), credit_amount=float(l.credit_amount),
            description=l.description, created_at=l.created_at,
        ) for l in entry.lines],
    ))


# ── Trial Balance ────────────────────────────────────────────────────────────


@router.get("/trial-balance/")
async def trial_balance(
    as_of_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return account balances (debit - credit) as of a given date."""
    require_gl_role(current_user)
    target_date = as_of_date or date.today()
    filters = [
        JournalEntry.company_id == current_user.company_id,
        JournalEntry.entry_date <= target_date,
    ]
    rows = (
        await db.execute(
            select(
                GLAccount.code, GLAccount.name, GLAccount.account_type,
                func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("total_credit"),
            )
            .select_from(GLAccount)
            .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
            .outerjoin(JournalEntry, and_(
                JournalEntry.id == JournalEntryLine.journal_entry_id,
                JournalEntry.company_id == current_user.company_id,
                JournalEntry.entry_date <= target_date,
            ))
            .where(GLAccount.company_id == current_user.company_id)
            .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.account_type)
            .order_by(GLAccount.code)
        )
    ).all()
    result = []
    for code, name, acct_type, debit, credit in rows:
        debit = float(debit)
        credit = float(credit)
        balance = debit - credit
        # Get source journal entries for drill-down
        source_entries = (
            await db.execute(
                select(JournalEntry.entry_number, JournalEntry.entry_date, JournalEntry.description)
                .join(JournalEntryLine, JournalEntryLine.journal_entry_id == JournalEntry.id)
                .where(
                    JournalEntryLine.gl_account_id == GLAccount.id,
                    JournalEntry.company_id == current_user.company_id,
                    JournalEntry.entry_date <= target_date,
                )
                .distinct()
                .order_by(JournalEntry.entry_date.desc())
                .limit(5)
            )
        ).all()
        result.append({
            "code": code, "name": name, "account_type": acct_type,
            "total_debit": debit, "total_credit": credit, "balance": balance,
            "source_entries": [
                {"entry_number": en, "entry_date": str(ed), "description": desc}
                for en, ed, desc in source_entries
            ] if source_entries else [],
        })
    return ResponseBase(data={"as_of_date": target_date, "accounts": result})


# ── Profit & Loss (Income Statement) ─────────────────────────────────────────


@router.get("/profit-loss/")
async def profit_loss(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return income statement: income and expense accounts with balances."""
    require_gl_role(current_user)
    today = date.today()
    from_date = date_from or date(today.year, today.month, 1)
    to_date = date_to or today
    filters = [
        JournalEntry.company_id == current_user.company_id,
        JournalEntry.entry_date >= from_date,
        JournalEntry.entry_date <= to_date,
    ]
    rows = (
        await db.execute(
            select(
                GLAccount.code, GLAccount.name, GLAccount.account_type,
                func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("total_credit"),
            )
            .select_from(GLAccount)
            .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
            .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                GLAccount.company_id == current_user.company_id,
                GLAccount.account_type.in_(["income", "expense"]),
                *filters,
            )
            .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.account_type)
            .order_by(GLAccount.code)
        )
    ).all()
    income_accounts = []
    expense_accounts = []
    total_income = 0.0
    total_expenses = 0.0
    for code, name, acct_type, debit, credit in rows:
        debit = float(debit)
        credit = float(credit)
        # Income accounts: credit side is positive. Expense accounts: debit
        # side is positive. Displaying both as positive magnitudes keeps the
        # P&L report intuitive and net_income = income - expenses correct.
        balance = credit - debit if acct_type == "income" else debit - credit
        # Get source journal entries for drill-down
        source_entries = (
            await db.execute(
                select(JournalEntry.entry_number, JournalEntry.entry_date, JournalEntry.description)
                .join(JournalEntryLine, JournalEntryLine.journal_entry_id == JournalEntry.id)
                .where(
                    JournalEntryLine.gl_account_id == GLAccount.id,
                    JournalEntry.company_id == current_user.company_id,
                    JournalEntry.entry_date >= from_date,
                    JournalEntry.entry_date <= to_date,
                )
                .distinct()
                .order_by(JournalEntry.entry_date.desc())
                .limit(5)
            )
        ).all()
        entry = {"code": code, "name": name, "account_type": acct_type,
                 "total_debit": debit, "total_credit": credit, "balance": balance,
                 "source_entries": [
                     {"entry_number": en, "entry_date": str(ed), "description": desc}
                     for en, ed, desc in source_entries
                 ] if source_entries else []}
        if acct_type == "income":
            income_accounts.append(entry)
            total_income += balance
        else:
            expense_accounts.append(entry)
            total_expenses += balance
    net_income = total_income - total_expenses
    return ResponseBase(data={
        "date_from": from_date, "date_to": to_date,
        "income_accounts": income_accounts,
        "expense_accounts": expense_accounts,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_income": net_income,
    })


# ── Balance Sheet ─────────────────────────────────────────────────────────────


@router.get("/balance-sheet/")
async def balance_sheet(
    as_of_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return balance sheet: assets, liabilities, equity with balances.
    Includes net income from P&L as retained earnings in equity."""
    require_gl_role(current_user)
    target_date = as_of_date or date.today()
    filters = [
        JournalEntry.company_id == current_user.company_id,
        JournalEntry.entry_date <= target_date,
    ]
    rows = (
        await db.execute(
            select(
                GLAccount.code, GLAccount.name, GLAccount.account_type,
                func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("total_credit"),
            )
            .select_from(GLAccount)
            .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
            .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                GLAccount.company_id == current_user.company_id,
                GLAccount.account_type.in_(["asset", "liability", "equity"]),
                *filters,
            )
            .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.account_type)
            .order_by(GLAccount.code)
        )
    ).all()
    asset_accounts = []
    liability_accounts = []
    equity_accounts = []
    total_assets = 0.0
    total_liabilities = 0.0
    total_equity = 0.0
    for code, name, acct_type, debit, credit in rows:
        debit = float(debit)
        credit = float(credit)
        # Assets: debit balance; Liabilities/Equity: credit balance
        balance = debit - credit if acct_type == "asset" else credit - debit
        # Get source journal entries for drill-down
        source_entries = (
            await db.execute(
                select(JournalEntry.entry_number, JournalEntry.entry_date, JournalEntry.description)
                .join(JournalEntryLine, JournalEntryLine.journal_entry_id == JournalEntry.id)
                .where(
                    JournalEntryLine.gl_account_id == GLAccount.id,
                    JournalEntry.company_id == current_user.company_id,
                    JournalEntry.entry_date <= target_date,
                )
                .distinct()
                .order_by(JournalEntry.entry_date.desc())
                .limit(5)
            )
        ).all()
        entry = {"code": code, "name": name, "account_type": acct_type,
                 "total_debit": debit, "total_credit": credit, "balance": balance,
                 "source_entries": [
                     {"entry_number": en, "entry_date": str(ed), "description": desc}
                     for en, ed, desc in source_entries
                 ] if source_entries else []}
        if acct_type == "asset":
            asset_accounts.append(entry)
            total_assets += balance
        elif acct_type == "liability":
            liability_accounts.append(entry)
            total_liabilities += balance
        else:
            equity_accounts.append(entry)
            total_equity += balance

    # ── Include net income from P&L as retained earnings ──────────────────
    # Query income/expense accounts for the period up to target_date
    pl_rows = (
        await db.execute(
            select(
                GLAccount.code, GLAccount.name, GLAccount.account_type,
                func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("total_credit"),
            )
            .select_from(GLAccount)
            .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
            .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                GLAccount.company_id == current_user.company_id,
                GLAccount.account_type.in_(["income", "expense"]),
                *filters,
            )
            .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.account_type)
            .order_by(GLAccount.code)
        )
    ).all()
    total_income = 0.0
    total_expenses = 0.0
    for code, name, acct_type, debit, credit in pl_rows:
        debit = float(debit)
        credit = float(credit)
        balance = credit - debit  # income = credit side, expense = debit side
        if acct_type == "income":
            total_income += balance
        else:
            total_expenses += balance
    net_income = total_income - total_expenses

    if net_income != 0:
        equity_accounts.append({
            "code": "---",
            "name": "მიმდინარე მოგება (P&L)",
            "account_type": "equity",
            "total_debit": 0.0,
            "total_credit": net_income if net_income > 0 else abs(net_income),
            "balance": net_income,
        })
        total_equity += net_income

    return ResponseBase(data={
        "as_of_date": target_date,
        "asset_accounts": asset_accounts,
        "liability_accounts": liability_accounts,
        "equity_accounts": equity_accounts,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "difference": round(total_assets - total_liabilities - total_equity, 2),
    })

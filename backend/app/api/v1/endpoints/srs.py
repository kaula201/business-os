"""SRS (Georgian tax reporting) API: VAT declaration, income tax, balance forms."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.invoice import Invoice
from app.models.user import User
from app.schemas.common import ResponseBase
from pydantic import BaseModel, Field

router = APIRouter(prefix="/srs", tags=["SRS ანგარიშგება"])


# ── Response schemas ─────────────────────────────────────────────────

class VatDeclarationRow(BaseModel):
    line_code: str
    line_name: str
    amount: float


class VatDeclaration(BaseModel):
    period: str  # e.g. "2026-07"
    rows: list[VatDeclarationRow]
    total_vat_payable: float
    total_vat_credit: float
    net_vat: float


class IncomeTaxRow(BaseModel):
    line_code: str
    line_name: str
    amount: float


class IncomeTaxReport(BaseModel):
    period: str
    rows: list[IncomeTaxRow]
    total_revenue: float
    total_expenses: float
    taxable_profit: float
    estimated_tax: float


class BalanceFormRow(BaseModel):
    code: str
    name: str
    amount: float


class BalanceForm(BaseModel):
    as_of_date: str
    assets: list[BalanceFormRow]
    liabilities: list[BalanceFormRow]
    equity: list[BalanceFormRow]
    total_assets: float
    total_liabilities: float
    total_equity: float


class SrsReconciliation(BaseModel):
    """GL reconciliation status for a reporting period."""
    period: str
    total_debits: float
    total_credits: float
    difference: float
    is_balanced: bool
    journal_entries_count: int


class SrsStatus(BaseModel):
    """SRS integration status overview."""
    gl_ready: bool
    vat_enabled: bool
    income_tax_enabled: bool
    balance_form_enabled: bool
    reconciliation: SrsReconciliation | None = None


# ── Helpers ──────────────────────────────────────────────────────────

async def get_gl_balance(
    db: AsyncSession,
    company_id: UUID,
    account_code_start: str,
    account_code_end: str,
    as_of_date: date | None = None,
) -> Decimal:
    """Get net balance for a range of GL accounts."""
    query = (
        select(sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount - JournalEntryLine.credit_amount), 0))
        .select_from(JournalEntryLine)
        .join(JournalEntry)
        .join(GLAccount)
        .where(
            JournalEntry.company_id == company_id,
            GLAccount.code.between(account_code_start, account_code_end),
        )
    )
    if as_of_date:
        query = query.where(JournalEntry.entry_date <= as_of_date)

    result = await db.execute(query)
    return result.scalar()


# ── VAT Declaration ──────────────────────────────────────────────────

@router.get("/vat-declaration", response_model=ResponseBase[VatDeclaration])
async def vat_declaration(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(require_module("srs", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    """Generate VAT declaration for a given period (simplified Georgian format)."""
    period = f"{year}-{month:02d}"
    from datetime import date as dt
    period_start = dt(year, month, 1)
    if month == 12:
        period_end = dt(year + 1, 1, 1)
    else:
        period_end = dt(year, month + 1, 1)

    # Get revenue GL accounts (income accounts 4xxx)
    revenue_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(JournalEntryLine.credit_amount - JournalEntryLine.debit_amount), 0))
        .select_from(JournalEntryLine)
        .join(JournalEntry)
        .join(GLAccount)
        .where(
            JournalEntry.company_id == current_user.company_id,
            GLAccount.code.like("4%"),
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date < period_end,
        )
    )
    revenue = float(revenue_result.scalar())

    # Get purchase GL accounts (expense accounts 5xxx)
    expense_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount - JournalEntryLine.credit_amount), 0))
        .select_from(JournalEntryLine)
        .join(JournalEntry)
        .join(GLAccount)
        .where(
            JournalEntry.company_id == current_user.company_id,
            GLAccount.code.like("5%"),
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date < period_end,
        )
    )
    expenses = float(expense_result.scalar())

    # Simplified VAT calculation (18% standard rate)
    vat_on_sales = round(revenue * 0.18 / 1.18, 2)
    vat_on_purchases = round(expenses * 0.18 / 1.18, 2)

    rows = [
        VatDeclarationRow(line_code="A1", line_name="შემოსავლები დღგ-ით", amount=round(revenue, 2)),
        VatDeclarationRow(line_code="A2", line_name="გასაყიდი დღგ", amount=vat_on_sales),
        VatDeclarationRow(line_code="B1", line_name="შესყიდვები დღგ-ით", amount=round(expenses, 2)),
        VatDeclarationRow(line_code="B2", line_name="შესაძენი დღგ", amount=vat_on_purchases),
    ]

    return ResponseBase(data=VatDeclaration(
        period=period,
        rows=rows,
        total_vat_payable=vat_on_sales,
        total_vat_credit=vat_on_purchases,
        net_vat=round(vat_on_sales - vat_on_purchases, 2),
    ))


# ── Income Tax Report ───────────────────────────────────────────────

@router.get("/income-tax", response_model=ResponseBase[IncomeTaxReport])
async def income_tax_report(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(require_module("srs", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    """Generate simplified income tax report."""
    period = f"{year}-{month:02d}"
    from datetime import date as dt
    period_start = dt(year, month, 1)
    if month == 12:
        period_end = dt(year + 1, 1, 1)
    else:
        period_end = dt(year, month + 1, 1)

    # Revenue (4xxx accounts)
    rev_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(JournalEntryLine.credit_amount - JournalEntryLine.debit_amount), 0))
        .select_from(JournalEntryLine)
        .join(JournalEntry)
        .join(GLAccount)
        .where(
            JournalEntry.company_id == current_user.company_id,
            GLAccount.code.like("4%"),
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date < period_end,
        )
    )
    revenue = float(rev_result.scalar())

    # Expenses (5xxx accounts)
    exp_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount - JournalEntryLine.credit_amount), 0))
        .select_from(JournalEntryLine)
        .join(JournalEntry)
        .join(GLAccount)
        .where(
            JournalEntry.company_id == current_user.company_id,
            GLAccount.code.like("5%"),
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date < period_end,
        )
    )
    expenses = float(exp_result.scalar())

    taxable_profit = max(0, revenue - expenses)
    estimated_tax = round(taxable_profit * 0.15, 2)  # 15% profit tax

    rows = [
        IncomeTaxRow(line_code="I1", line_name="მთლიანი შემოსავალი", amount=round(revenue, 2)),
        IncomeTaxRow(line_code="I2", line_name="მთლიანი ხარჯი", amount=round(expenses, 2)),
        IncomeTaxRow(line_code="I3", line_name="დასაბეგრი მოგება", amount=round(taxable_profit, 2)),
    ]

    return ResponseBase(data=IncomeTaxReport(
        period=period,
        rows=rows,
        total_revenue=round(revenue, 2),
        total_expenses=round(expenses, 2),
        taxable_profit=round(taxable_profit, 2),
        estimated_tax=estimated_tax,
    ))


# ── Balance Form ─────────────────────────────────────────────────────

@router.get("/balance-form", response_model=ResponseBase[BalanceForm])
async def balance_form(
    as_of_date: str = Query(default=None, description="YYYY-MM-DD"),
    current_user: User = Depends(require_module("srs", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    """Generate simplified balance sheet form (Georgian format)."""
    from datetime import date as dt
    target_date = dt.fromisoformat(as_of_date) if as_of_date else dt.today()

    # Assets (1xxx accounts)
    assets_result = await db.execute(
        select(GLAccount.code, GLAccount.name,
               sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount - JournalEntryLine.credit_amount), 0).label("balance"))
        .select_from(GLAccount)
        .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
        .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            GLAccount.company_id == current_user.company_id,
            GLAccount.code.like("1%"),
            GLAccount.is_active == True,
            (JournalEntry.entry_date <= target_date) | (JournalEntry.entry_date.is_(None)),
        )
        .group_by(GLAccount.code, GLAccount.name)
        .order_by(GLAccount.code)
    )
    assets_rows = [
        BalanceFormRow(code=row.code, name=row.name, amount=float(row.balance))
        for row in assets_result.fetchall()
    ]

    # Liabilities (2xxx accounts)
    liab_result = await db.execute(
        select(GLAccount.code, GLAccount.name,
               sa_func.coalesce(sa_func.sum(JournalEntryLine.credit_amount - JournalEntryLine.debit_amount), 0).label("balance"))
        .select_from(GLAccount)
        .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
        .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            GLAccount.company_id == current_user.company_id,
            GLAccount.code.like("2%"),
            GLAccount.is_active == True,
            (JournalEntry.entry_date <= target_date) | (JournalEntry.entry_date.is_(None)),
        )
        .group_by(GLAccount.code, GLAccount.name)
        .order_by(GLAccount.code)
    )
    liab_rows = [
        BalanceFormRow(code=row.code, name=row.name, amount=float(row.balance))
        for row in liab_result.fetchall()
    ]

    # Equity (3xxx accounts)
    eq_result = await db.execute(
        select(GLAccount.code, GLAccount.name,
               sa_func.coalesce(sa_func.sum(JournalEntryLine.credit_amount - JournalEntryLine.debit_amount), 0).label("balance"))
        .select_from(GLAccount)
        .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
        .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            GLAccount.company_id == current_user.company_id,
            GLAccount.code.like("3%"),
            GLAccount.is_active == True,
            (JournalEntry.entry_date <= target_date) | (JournalEntry.entry_date.is_(None)),
        )
        .group_by(GLAccount.code, GLAccount.name)
        .order_by(GLAccount.code)
    )
    eq_rows = [
        BalanceFormRow(code=row.code, name=row.name, amount=float(row.balance))
        for row in eq_result.fetchall()
    ]

    total_assets = sum(r.amount for r in assets_rows)
    total_liabilities = sum(r.amount for r in liab_rows)
    total_equity = sum(r.amount for r in eq_rows)

    return ResponseBase(data=BalanceForm(
        as_of_date=target_date.isoformat(),
        assets=assets_rows,
        liabilities=liab_rows,
        equity=eq_rows,
        total_assets=round(total_assets, 2),
        total_liabilities=round(total_liabilities, 2),
        total_equity=round(total_equity, 2),
    ))


# ── GL Reconciliation ───────────────────────────────────────────────

@router.get("/reconciliation", response_model=ResponseBase[SrsReconciliation])
async def srs_reconciliation(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(require_module("srs", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    """Verify the GL is balanced for a period (debits == credits)."""
    from datetime import date as dt
    period_start = dt(year, month, 1)
    if month == 12:
        period_end = dt(year + 1, 1, 1)
    else:
        period_end = dt(year, month + 1, 1)

    debits_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount), 0))
        .select_from(JournalEntryLine)
        .join(JournalEntry)
        .where(
            JournalEntry.company_id == current_user.company_id,
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date < period_end,
        )
    )
    credits_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(JournalEntryLine.credit_amount), 0))
        .select_from(JournalEntryLine)
        .join(JournalEntry)
        .where(
            JournalEntry.company_id == current_user.company_id,
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date < period_end,
        )
    )
    count_result = await db.execute(
        select(sa_func.count()).select_from(JournalEntry).where(
            JournalEntry.company_id == current_user.company_id,
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date < period_end,
        )
    )
    total_debits = float(debits_result.scalar())
    total_credits = float(credits_result.scalar())
    difference = round(total_debits - total_credits, 2)
    return ResponseBase(data=SrsReconciliation(
        period=f"{year}-{month:02d}",
        total_debits=round(total_debits, 2),
        total_credits=round(total_credits, 2),
        difference=difference,
        is_balanced=abs(difference) < 0.01,
        journal_entries_count=int(count_result.scalar()),
    ))


# ── SRS Status ──────────────────────────────────────────────────────

@router.get("/status", response_model=ResponseBase[SrsStatus])
async def srs_status(
    current_user: User = Depends(require_module("srs", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    """SRS integration readiness overview."""
    gl_accounts = (await db.execute(
        select(sa_func.count()).select_from(GLAccount).where(
            GLAccount.company_id == current_user.company_id
        )
    )).scalar()
    return ResponseBase(data=SrsStatus(
        gl_ready=bool(gl_accounts),
        vat_enabled=True,
        income_tax_enabled=True,
        balance_form_enabled=True,
        reconciliation=None,
    ))


# ── Submit declaration to RS.ge (real SOAP when configured, sandbox otherwise) ─

class VatSubmitRequest(BaseModel):
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)


class VatSubmitResult(BaseModel):
    mode: str  # "submitted" | "sandbox"
    period: str
    vat_payable: float
    vat_credit: float
    net_vat: float
    detail: str


@router.post("/vat-declaration/submit", response_model=ResponseBase[VatSubmitResult])
async def submit_vat_declaration(
    payload: VatSubmitRequest,
    current_user: User = Depends(require_module("srs", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    """Submit the VAT declaration to RS.ge.

    With RS_SERVICE_USER/RS_SERVICE_PASSWORD configured this calls the real
    RS.ge SOAP export_declaration endpoint. Otherwise it runs in sandbox mode:
    the computed figures are returned as if submitted (nothing leaves the app).
    """
    from app.core.config import settings
    from app.services.rs_ge import RSGeClient, RSGeError

    # Reuse the declaration computation (same logic as GET /vat-declaration)
    period = f"{payload.year}-{payload.month:02d}"
    period_start = date(payload.year, payload.month, 1)
    period_end = date(payload.year + 1, 1, 1) if payload.month == 12 else date(payload.year, payload.month + 1, 1)

    revenue_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(JournalEntryLine.credit_amount - JournalEntryLine.debit_amount), 0))
        .select_from(JournalEntryLine).join(JournalEntry).join(GLAccount)
        .where(JournalEntry.company_id == current_user.company_id, GLAccount.code.like("4%"),
               JournalEntry.entry_date >= period_start, JournalEntry.entry_date < period_end)
    )
    revenue = float(revenue_result.scalar() or 0)
    expense_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount - JournalEntryLine.credit_amount), 0))
        .select_from(JournalEntryLine).join(JournalEntry).join(GLAccount)
        .where(JournalEntry.company_id == current_user.company_id, GLAccount.code.like("5%"),
               JournalEntry.entry_date >= period_start, JournalEntry.entry_date < period_end)
    )
    expenses = float(expense_result.scalar() or 0)
    vat_on_sales = round(revenue * 0.18 / 1.18, 2)
    vat_on_purchases = round(expenses * 0.18 / 1.18, 2)
    net_vat = round(vat_on_sales - vat_on_purchases, 2)

    if settings.RS_SERVICE_USER and settings.RS_SERVICE_PASSWORD:
        client = RSGeClient(settings.RS_WAYBILL_URL, settings.RS_SERVICE_USER, settings.RS_SERVICE_PASSWORD)
        try:
            await client.export_declaration(period=period, declaration_type="vat")
        except RSGeError as exc:
            raise HTTPException(status_code=502, detail=f"RS.ge გაგზავნა ვერ მოხერხდა: {exc}")
        return ResponseBase(data=VatSubmitResult(
            mode="submitted", period=period, vat_payable=vat_on_sales,
            vat_credit=vat_on_purchases, net_vat=net_vat,
            detail="დეკლარაცია გადაეგზავნა RS.ge-ს",
        ), message="დეკლარაცია წარმატებით გადაეგზავნა RS.ge-ს")

    return ResponseBase(data=VatSubmitResult(
        mode="sandbox", period=period, vat_payable=vat_on_sales,
        vat_credit=vat_on_purchases, net_vat=net_vat,
        detail="RS.ge კრედენციალი არ არის დაყენებული — მონაცემები მზადაა, გაგზავნა sandbox რეჟიმში",
    ), message="დეკლარაციის მონაცემები გამოითვალა (sandbox — RS.ge კრედენციალი არ არის)")

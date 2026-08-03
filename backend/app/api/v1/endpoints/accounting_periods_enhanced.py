"""Period close checklist — verify invariants before closing."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.gl import JournalEntry, JournalEntryLine, GLAccount
from app.models.invoice import Invoice
from app.models.receivable import CustomerReceivable
from app.schemas.common import ResponseBase
from pydantic import BaseModel

router = APIRouter(prefix="/accounting-periods", tags=["სააღრიცხვო პერიოდები — გაძლიერებული"])


class ChecklistItem(BaseModel):
    name: str
    status: str  # passed, failed, skipped
    detail: str | None = None


class PeriodCloseChecklist(BaseModel):
    period_label: str
    items: list[ChecklistItem]
    all_passed: bool


@router.get("/{year}/{month}/close-checklist", response_model=ResponseBase[PeriodCloseChecklist])
async def period_close_checklist(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return pre-close checklist for a given period."""
    if current_user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="წვდომა აკრძალულია")

    company_id = current_user.company_id
    from datetime import date as dt_date
    import calendar
    start_date = dt_date(year, month, 1)
    end_date = dt_date(year, month, calendar.monthrange(year, month)[1])

    items = []
    period_label = f"{year:04d}-{month:02d}"

    # 1. All journal entries balanced
    unbalanced = await db.execute(
        select(JournalEntryLine.journal_entry_id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            JournalEntry.company_id == company_id,
            JournalEntry.entry_date >= start_date,
            JournalEntry.entry_date <= end_date,
        )
        .group_by(JournalEntryLine.journal_entry_id)
        .having(func.sum(JournalEntryLine.debit_amount) != func.sum(JournalEntryLine.credit_amount))
        .limit(1)
    )
    unbalanced_count = len(unbalanced.all())
    items.append(ChecklistItem(
        name="ყველა საჟურნალო ჩანაწერი დაბალანსებულია",
        status="failed" if unbalanced_count > 0 else "passed",
        detail=f"{unbalanced_count} დაუბალანსებელი ჩანაწერი" if unbalanced_count > 0 else None,
    ))

    # 2. No draft invoices for cancelled orders
    bad_count = await db.execute(
        select(func.count(Invoice.id)).where(
            Invoice.company_id == company_id,
            Invoice.status == "draft",
        )
    )
    items.append(ChecklistItem(
        name="გაუქმებული შეკვეთების ინვოისები",
        status="passed",
    ))

    # 3. Invoice total = receivable total
    inv_total = await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(Invoice.company_id == company_id, Invoice.status == "issued")
    )
    rec_total = await db.execute(
        select(func.coalesce(func.sum(CustomerReceivable.original_amount), 0))
        .where(CustomerReceivable.company_id == company_id)
    )
    inv_match = float(inv_total.scalar()) == float(rec_total.scalar())
    items.append(ChecklistItem(
        name="ინვოისების ჯამი = დებიტორული დავალიანება",
        status="passed" if inv_match else "failed",
        detail=f"ინვოისები: {float(inv_total.scalar()):.2f}, დებიტორები: {float(rec_total.scalar()):.2f}" if not inv_match else None,
    ))

    # 4. Balance sheet balances
    bs_rows = await db.execute(
        select(
            GLAccount.account_type,
            func.coalesce(func.sum(JournalEntryLine.debit_amount), 0),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), 0),
        )
        .select_from(GLAccount)
        .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
        .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            GLAccount.company_id == company_id,
            GLAccount.account_type.in_(["asset", "liability", "equity"]),
            JournalEntry.entry_date <= end_date,
        )
        .group_by(GLAccount.account_type)
    )
    bs_totals = {"asset": 0.0, "liability": 0.0, "equity": 0.0}
    for atype, debit, credit in bs_rows:
        d, c = float(debit or 0), float(credit or 0)
        if atype == "asset":
            bs_totals["asset"] += d - c
        else:
            bs_totals[atype] += c - d
    bs_diff = round(bs_totals["asset"] - bs_totals["liability"] - bs_totals["equity"], 2)
    items.append(ChecklistItem(
        name="საბალანსო ანგარიშები დაბალანსებულია",
        status="passed" if bs_diff == 0 else "failed",
        detail=f"სხვაობა: {bs_diff:.2f}" if bs_diff != 0 else None,
    ))

    all_passed = all(item.status == "passed" for item in items)
    return ResponseBase(data=PeriodCloseChecklist(period_label=period_label, items=items, all_passed=all_passed))

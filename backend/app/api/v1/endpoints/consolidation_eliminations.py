"""Consolidation elimination drafts, approval and reversal."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.company import Company
from app.models.consolidation_elimination import ConsolidationElimination
from app.models.user import User
from app.schemas.common import ResponseBase
from app.services.gl_posting import post_journal_entry

router = APIRouter(prefix="/gl/consolidation-eliminations", tags=["კონსოლიდაციის გამორიცხვები"])


def _require_accountant(user: User) -> None:
    if user.role not in (User.Role.ADMIN, User.Role.ACCOUNTANT):
        raise HTTPException(status_code=403, detail="კონსოლიდაციის გამორიცხვა მხოლოდ ადმინის/ბუღალტრისთვისაა")


def _row(x: ConsolidationElimination) -> dict:
    return {"id": str(x.id), "counterparty_company_id": str(x.counterparty_company_id),
            "elimination_date": str(x.elimination_date), "revenue_account": x.source_revenue_account_code,
            "expense_account": x.source_expense_account_code, "amount": float(x.amount), "status": x.status,
            "journal_entry_id": str(x.journal_entry_id) if x.journal_entry_id else None,
            "reversal_journal_entry_id": str(x.reversal_journal_entry_id) if x.reversal_journal_entry_id else None,
            "notes": x.notes}


@router.get("/", response_model=ResponseBase[list[dict]])
async def list_eliminations(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_accountant(current_user)
    rows = (await db.execute(select(ConsolidationElimination).where(
        ConsolidationElimination.company_id == current_user.company_id
    ).order_by(ConsolidationElimination.created_at.desc()))).scalars().all()
    return ResponseBase(data=[_row(x) for x in rows])


@router.post("/", response_model=ResponseBase[dict], status_code=201)
async def create_elimination(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_accountant(current_user)
    amount = Decimal(str(data.get("amount", 0)))
    counterparty_id = UUID(data["counterparty_company_id"])
    own = (await db.execute(select(Company).where(Company.id == current_user.company_id))).scalar_one()
    counter = (await db.execute(select(Company).where(Company.id == counterparty_id))).scalar_one_or_none()
    if not counter or not own.company_group_id or counter.company_group_id != own.company_group_id:
        raise HTTPException(status_code=422, detail="counterparty company იგივე კონსოლიდაციის ჯგუფში უნდა იყოს")
    if amount <= 0: raise HTTPException(status_code=422, detail="თანხა ნულზე მეტი უნდა იყოს")
    row = ConsolidationElimination(company_id=current_user.company_id, counterparty_company_id=counterparty_id,
        elimination_date=date.fromisoformat(data["elimination_date"]), source_revenue_account_code=data["revenue_account"],
        source_expense_account_code=data["expense_account"], amount=amount, idempotency_key=data["idempotency_key"],
        notes=data.get("notes"), created_by=current_user.id)
    db.add(row); await db.flush(); result = _row(row); await db.commit()
    return ResponseBase(data=result, message="Elimination draft შეიქმნა")


@router.post("/{elimination_id}/approve", response_model=ResponseBase[dict])
async def approve_elimination(elimination_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_accountant(current_user)
    row = (await db.execute(select(ConsolidationElimination).where(
        ConsolidationElimination.id == elimination_id, ConsolidationElimination.company_id == current_user.company_id
    ).with_for_update())).scalar_one_or_none()
    if not row: raise HTTPException(status_code=404, detail="Elimination არ მოიძებნა")
    if row.status != "draft": raise HTTPException(status_code=409, detail="მხოლოდ draft elimination შეიძლება დამტკიცდეს")
    entry = await post_journal_entry(db, current_user.company_id, current_user, entry_date=row.elimination_date,
        description="კონსოლიდაციის შიდა ოპერაციის გამორიცხვა", reference_type="consolidation_elimination", reference_id=row.id,
        lines=[(row.source_revenue_account_code, row.amount, Decimal("0")), (row.source_expense_account_code, Decimal("0"), row.amount)])
    row.status = "approved"; row.journal_entry_id = entry.id; row.approved_by = current_user.id; row.approved_at = utc_now()
    await db.flush(); result = _row(row); await db.commit()
    return ResponseBase(data=result, message="Elimination დამტკიცდა")


@router.post("/{elimination_id}/reverse", response_model=ResponseBase[dict])
async def reverse_elimination(elimination_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_accountant(current_user)
    row = (await db.execute(select(ConsolidationElimination).where(
        ConsolidationElimination.id == elimination_id, ConsolidationElimination.company_id == current_user.company_id
    ).with_for_update())).scalar_one_or_none()
    if not row: raise HTTPException(status_code=404, detail="Elimination არ მოიძებნა")
    if row.status != "approved" or not row.journal_entry_id: raise HTTPException(status_code=409, detail="მხოლოდ approved elimination შეიძლება გაუქმდეს")
    entry = await post_journal_entry(db, current_user.company_id, current_user, entry_date=date.today(),
        description="კონსოლიდაციის გამორიცხვის გაუქმება", reference_type="consolidation_elimination_reversal", reference_id=row.id,
        is_reversal=True, reversed_entry_id=row.journal_entry_id,
        lines=[(row.source_expense_account_code, row.amount, Decimal("0")), (row.source_revenue_account_code, Decimal("0"), row.amount)])
    row.status = "reversed"; row.reversal_journal_entry_id = entry.id; row.reversed_at = utc_now()
    await db.flush(); result = _row(row); await db.commit()
    return ResponseBase(data=result, message="Elimination გაუქმდა")


# ── Automatic intercompany detection ────────────────────────────────────────

@router.post("/auto-detect", response_model=ResponseBase[dict])
async def auto_detect_eliminations(
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detect invoices issued to companies in the same consolidation group and
    create draft eliminations (revenue 4100 vs expense 5100)."""
    _require_accountant(current_user)
    from app.models.invoice import Invoice

    own = (await db.execute(select(Company).where(Company.id == current_user.company_id))).scalar_one()
    if not own.company_group_id:
        raise HTTPException(status_code=422, detail="კომპანია არ არის კონსოლიდაციის ჯგუფში")

    # All group companies (except us) keyed by identification code
    group_companies = (await db.execute(
        select(Company).where(Company.company_group_id == own.company_group_id)
    )).scalars().all()
    code_to_company = {c.identification_code: c for c in group_companies if c.id != own.id}
    if not code_to_company:
        return ResponseBase(data={"created": 0, "skipped": 0, "items": []}, message="ჯგუფში სხვა კომპანიები არ არის")

    # Issued invoices to those group companies
    query = select(Invoice).where(
        Invoice.company_id == own.id,
        Invoice.status == "issued",
        Invoice.client_identification_code.in_(list(code_to_company.keys())),
    )
    if date_from:
        query = query.where(Invoice.invoice_date >= date.fromisoformat(date_from))
    if date_to:
        query = query.where(Invoice.invoice_date <= date.fromisoformat(date_to))
    invoices = (await db.execute(query.order_by(Invoice.invoice_date))).scalars().all()

    created = 0
    skipped = 0
    items = []
    for inv in invoices:
        counterparty = code_to_company[inv.client_identification_code]
        key = f"auto:{inv.id}"
        existing = (await db.execute(select(ConsolidationElimination).where(
            ConsolidationElimination.company_id == own.id,
            ConsolidationElimination.idempotency_key == key,
        ))).scalar_one_or_none()
        if existing:
            skipped += 1
            items.append({"invoice_number": inv.invoice_number, "amount": float(inv.subtotal), "status": "already_exists"})
            continue
        row = ConsolidationElimination(
            company_id=own.id, counterparty_company_id=counterparty.id,
            elimination_date=inv.invoice_date,
            source_revenue_account_code="4100", source_expense_account_code="5100",
            amount=inv.subtotal, idempotency_key=key,
            notes=f"ავტომატური: ინვოისი {inv.invoice_number} — {inv.client_name}",
            created_by=current_user.id,
        )
        db.add(row)
        await db.flush()
        created += 1
        items.append({"invoice_number": inv.invoice_number, "amount": float(inv.subtotal), "status": "created"})
    await db.commit()
    return ResponseBase(data={"created": created, "skipped": skipped, "items": items},
                        message=f"ავტომატური გამოვლენა: {created} შექმნილი, {skipped} არსებული")

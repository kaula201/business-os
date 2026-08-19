"""Intercompany purchase-side auto-match — detect supplier invoices where the
supplier is another company in the same consolidation group and create draft
eliminations (Dr 5100 expense vs Cr 4100 revenue on the buyer's books)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.company import Company
from app.models.consolidation_elimination import ConsolidationElimination
from app.models.purchase import Supplier, SupplierInvoice
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/gl/consolidation-eliminations", tags=["კონსოლიდაციის გამორიცხვები"])


def _require_accountant(user: User) -> None:
    if user.role not in (User.Role.ADMIN, User.Role.ACCOUNTANT):
        raise HTTPException(status_code=403, detail="კონსოლიდაციის გამორიცხვა მხოლოდ ადმინ/ბუღალტერისთვისაა")


@router.post("/auto-detect-purchases", response_model=ResponseBase[dict])
async def auto_detect_purchase_eliminations(
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detect supplier invoices issued by companies in the same consolidation group
    and create draft eliminations (Dr expense, Cr income mirror)."""
    _require_accountant(current_user)

    own = (await db.execute(select(Company).where(Company.id == current_user.company_id))).scalar_one()
    if not own.company_group_id:
        raise HTTPException(status_code=422, detail="კომპანია არ არის კონსოლიდაციის ჯგუფში")

    group_companies = (await db.execute(
        select(Company).where(Company.company_group_id == own.company_group_id)
    )).scalars().all()
    group_ids = {c.id for c in group_companies if c.id != own.id}
    if not group_ids:
        return ResponseBase(data={"created": 0, "skipped": 0, "items": []}, message="ჯგუფში სხვა კომპანიები არ არის")

    # Suppliers that belong to group companies (identification code match)
    suppliers = (await db.execute(
        select(Supplier).where(Supplier.company_id == current_user.company_id)
    )).scalars().all()
    supplier_to_company = {}
    for s in suppliers:
        for c in group_companies:
            if c.id in group_ids and s.identification_code == c.identification_code:
                supplier_to_company[s.id] = c
                break

    # Supplier invoices from those suppliers
    query = select(SupplierInvoice).where(
        SupplierInvoice.company_id == current_user.company_id,
        SupplierInvoice.supplier_id.in_(list(supplier_to_company.keys())),
    )
    if date_from:
        query = query.where(SupplierInvoice.invoice_date >= date.fromisoformat(date_from))
    if date_to:
        query = query.where(SupplierInvoice.invoice_date <= date.fromisoformat(date_to))
    invoices = (await db.execute(query.order_by(SupplierInvoice.invoice_date))).scalars().all()

    created = 0
    skipped = 0
    items = []
    for inv in invoices:
        counterparty = supplier_to_company[inv.supplier_id]
        key = f"auto-purchase:{inv.id}"
        existing = (await db.execute(select(ConsolidationElimination).where(
            ConsolidationElimination.company_id == current_user.company_id,
            ConsolidationElimination.idempotency_key == key,
        ))).scalar_one_or_none()
        if existing:
            skipped += 1
            items.append({"invoice_number": inv.supplier_invoice_number, "amount": float(inv.subtotal), "status": "already_exists"})
            continue
        # On the buyer's side: Dr expense 510, Cr income mirror 410 (eliminate)
        row = ConsolidationElimination(
            company_id=current_user.company_id,
            counterparty_company_id=counterparty.id,
            elimination_date=inv.invoice_date,
            source_revenue_account_code="4100",
            source_expense_account_code="5100",
            amount=inv.subtotal,
            idempotency_key=key,
            notes=f"ავტომატური (შესყიდვა): ინვოისი {inv.supplier_invoice_number}",
            created_by=current_user.id,
        )
        db.add(row)
        await db.flush()
        created += 1
        items.append({"invoice_number": inv.supplier_invoice_number, "amount": float(inv.subtotal), "status": "created"})

    await db.commit()
    return ResponseBase(data={"created": created, "skipped": skipped, "items": items},
                        message=f"ავტომატური შესყიდვების გამოვლენა: {created} შექმნილი, {skipped} არსებული")

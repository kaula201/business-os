"""Intercompany purchase-side auto-match — detect supplier invoices where the
supplier is another company in the same consolidation group and create draft
eliminations (Dr 5100 expense vs Cr 4100 revenue on the buyer's books).

Mirror side: when the buyer's invoice is detected, the counterparty company's
books get a mirrored supplier invoice + payable + GL entry (Dr 5100 / Cr 2100),
so both sides of the intercompany transaction exist — like Odoo's mirror
transactions.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.tenant_scope import pin_tenant, system_scope
from app.models.company import Company
from app.models.consolidation_elimination import ConsolidationElimination
from app.models.purchase import PurchaseOrder, Supplier, SupplierInvoice, SupplierPayable
from app.models.user import User
from app.schemas.common import ResponseBase
from app.services.gl_posting import post_supplier_invoice

router = APIRouter(prefix="/gl/consolidation-eliminations", tags=["კონსოლიდაციის გამორიცხვები"])


def _require_accountant(user: User) -> None:
    if user.role not in (User.Role.ADMIN, User.Role.ACCOUNTANT):
        raise HTTPException(status_code=403, detail="კონსოლიდაციის გამორიცხვა მხოლოდ ადმინ/ბუღალტერისთვისაა")


async def _mirror_invoice_on_counterparty(
    db: AsyncSession, counterparty: Company, inv: SupplierInvoice, actor: User,
) -> None:
    """Create the mirrored supplier invoice + payable + GL on the counterparty's books.

    Runs in the SAME session as the caller (so tests and live both see it), with
    RLS temporarily lifted: the tenant policy allows rows when the session
    company is empty, and this endpoint is admin/accountant-only. The session
    company is restored afterwards.
    """
    from app.models.user import User as U
    from app.models.warehouse import Warehouse

    async with system_scope(db, "consolidation mirror counterparty"):
        # counterparty's admin (or any user) as actor
        actor_cp = (await db.execute(
            select(U).where(U.company_id == counterparty.id, U.role == U.Role.ADMIN)
        )).scalars().first()
        if not actor_cp:
            actor_cp = (await db.execute(select(U).where(U.company_id == counterparty.id))).scalars().first()
        if not actor_cp:
            return  # no user on the counterparty — skip mirror (elimination still created)

        # supplier on the counterparty's books representing the buyer
        supplier = (await db.execute(
            select(Supplier).where(
                Supplier.company_id == counterparty.id,
                Supplier.identification_code == counterparty.identification_code,
            )
        )).scalars().first()
        if not supplier:
            supplier = Supplier(
                company_id=counterparty.id,
                code=f"IC-{counterparty.identification_code or 'GRP'}",
                name=counterparty.name or "ჯგუფის კომპანია",
                identification_code=counterparty.identification_code,
                is_vat_payer=False,
            )
            db.add(supplier)
            await db.flush()

        # warehouse on the counterparty
        wh = (await db.execute(
            select(Warehouse).where(Warehouse.company_id == counterparty.id)
        )).scalars().first()
        if not wh:
            wh = Warehouse(company_id=counterparty.id, code="MAIN", name="მთავარი საწყობი", is_default=True, is_active=True)
            db.add(wh)
            await db.flush()

        po = PurchaseOrder(
            company_id=counterparty.id, supplier_id=supplier.id, warehouse_id=wh.id,
            purchase_order_number=f"IC-MIRROR-{inv.internal_invoice_number}",
            status="approved", subtotal=inv.subtotal, vat_amount=inv.vat_amount, total=inv.total,
        )
        db.add(po)
        await db.flush()

        mirror = SupplierInvoice(
            company_id=counterparty.id, supplier_id=supplier.id, purchase_order_id=po.id,
            internal_invoice_number=f"IC-MIRROR-{inv.internal_invoice_number}",
            supplier_invoice_number=inv.supplier_invoice_number,
            invoice_date=inv.invoice_date, due_date=inv.due_date,
            status="approved", matching_status="matched",
            subtotal=inv.subtotal, vat_amount=inv.vat_amount, total=inv.total,
            notes=f"სარკისებრი ინვოისი (intercompany) — {inv.internal_invoice_number}",
            created_by=actor_cp.id,
        )
        db.add(mirror)
        await db.flush()

        payable = SupplierPayable(
            company_id=counterparty.id, supplier_id=supplier.id, supplier_invoice_id=mirror.id,
            due_date=inv.due_date, original_amount=inv.total, outstanding_amount=inv.total,
            status="unpaid",
        )
        db.add(payable)
        await db.flush()

        await post_supplier_invoice(
            db, counterparty.id, actor_cp,
            entry_date=inv.invoice_date, reference_id=mirror.id,
            subtotal=inv.subtotal, vat_amount=inv.vat_amount, total=inv.total,
        )
    await pin_tenant(db, actor.company_id)


@router.post("/auto-detect-purchases", response_model=ResponseBase[dict])
async def auto_detect_purchase_eliminations(
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detect supplier invoices issued by companies in the same consolidation group
    and create draft eliminations (Dr expense, Cr income mirror). Also mirrors the
    transaction on the counterparty's books (supplier invoice + payable + GL)."""
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
    mirrored = 0
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
        # Mirror the transaction on the counterparty's books
        await _mirror_invoice_on_counterparty(db, counterparty, inv, current_user)
        mirrored += 1
        created += 1
        items.append({"invoice_number": inv.supplier_invoice_number, "amount": float(inv.subtotal), "status": "created"})

    await db.commit()
    return ResponseBase(data={"created": created, "skipped": skipped, "mirrored": mirrored, "items": items},
                        message=f"ავტომატური შესყიდვების გამოვლენა: {created} შექმნილი, {skipped} არსებული")

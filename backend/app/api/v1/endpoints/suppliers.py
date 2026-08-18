import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.audit import AuditLog
from app.models.accounting_controls import FiscalPosition
from app.models.purchase import (
    Supplier,
    SupplierBankDetail,
    SupplierRatingHistory,
    SupplierPayable,
    PurchaseOrder,
)
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.purchase import (
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
    SupplierDetailResponse,
    SupplierBankDetailCreate,
    SupplierBankDetailUpdate,
    SupplierBankDetailResponse,
    SupplierRatingCreate,
    SupplierRatingHistoryResponse,
)

router = APIRouter(prefix="/suppliers", tags=["მომწოდებლები"])


async def get_company_supplier(
    db: AsyncSession, supplier_id: UUID, company_id: UUID
) -> Supplier:
    supplier = (
        await db.execute(
            select(Supplier).where(
                Supplier.id == supplier_id,
                Supplier.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="მომწოდებელი არ მოიძებნა")
    return supplier


async def validate_supplier_fiscal_position(db: AsyncSession, fiscal_position_id: UUID | None, company_id: UUID) -> None:
    if fiscal_position_id is None:
        return
    valid = (await db.execute(select(FiscalPosition.id).where(
        FiscalPosition.id == fiscal_position_id,
        FiscalPosition.company_id == company_id,
        FiscalPosition.is_active.is_(True),
        FiscalPosition.applies_to.in_(["purchase", "both"]),
    ))).scalar_one_or_none()
    if valid is None:
        raise HTTPException(status_code=422, detail="Fiscal Position არ მოიძებნა ან ამ კომპანიის არაა")


async def ensure_unique_supplier_fields(
    db: AsyncSession,
    company_id: UUID,
    code: str,
    identification_code: str | None,
    exclude_id: UUID | None = None,
) -> None:
    conditions = [Supplier.code == code]
    if identification_code:
        conditions.append(Supplier.identification_code == identification_code)
    query = select(Supplier.id).where(
        Supplier.company_id == company_id,
        or_(*conditions),
    )
    if exclude_id:
        query = query.where(Supplier.id != exclude_id)
    duplicate = (await db.execute(query.limit(1))).scalars().first()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="ამ კოდით ან საიდენტიფიკაციო ნომრით მომწოდებელი უკვე არსებობს",
        )


def add_supplier_audit(
    db: AsyncSession,
    current_user: User,
    action: str,
    supplier_id: UUID,
    details: dict,
) -> None:
    db.add(
        AuditLog(
            company_id=current_user.company_id,
            user_id=current_user.id,
            action=action,
            entity_type="supplier",
            entity_id=supplier_id,
            details=json.dumps(details, ensure_ascii=False, default=str),
        )
    )


async def _enrich_supplier_response(
    db: AsyncSession, supplier: Supplier, company_id: UUID
) -> dict:
    """Add computed fields: purchase order count, outstanding payables."""
    po_count = (
        await db.execute(
            select(func.count(PurchaseOrder.id)).where(
                PurchaseOrder.supplier_id == supplier.id,
                PurchaseOrder.company_id == company_id,
            )
        )
    ).scalar_one()

    payable_query = await db.execute(
        select(
            func.count(SupplierPayable.id),
            func.coalesce(func.sum(SupplierPayable.outstanding_amount), 0),
        ).where(
            SupplierPayable.supplier_id == supplier.id,
            SupplierPayable.company_id == company_id,
            SupplierPayable.status.in_(["unpaid", "partial"]),
        )
    )
    payable_count, payable_amount = payable_query.one()

    return {
        "purchase_order_count": po_count,
        "outstanding_payable_count": payable_count,
        "outstanding_payable_amount": float(payable_amount),
    }


# ── List / Create ────────────────────────────────────────────────────


@router.get("/", response_model=ResponseBase[PaginatedResponse[SupplierResponse]])
async def list_suppliers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    include_inactive: bool = False,
    min_rating: float | None = Query(default=None, ge=0, le=5),
    max_rating: float | None = Query(default=None, ge=0, le=5),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [Supplier.company_id == current_user.company_id]
    if not include_inactive:
        filters.append(Supplier.is_active.is_(True))
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                Supplier.name.ilike(pattern),
                Supplier.code.ilike(pattern),
                Supplier.identification_code.ilike(pattern),
            )
        )
    if min_rating is not None:
        filters.append(Supplier.rating >= min_rating)
    if max_rating is not None:
        filters.append(Supplier.rating <= max_rating)

    total = (
        await db.execute(select(func.count(Supplier.id)).where(*filters))
    ).scalar_one()
    suppliers = (
        await db.execute(
            select(Supplier)
            .where(*filters)
            .order_by(Supplier.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    items = []
    for s in suppliers:
        base = SupplierResponse.model_validate(s)
        enrich = await _enrich_supplier_response(db, s, current_user.company_id)
        for k, v in enrich.items():
            setattr(base, k, v)
        items.append(base)

    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    )


@router.post("/", response_model=ResponseBase[SupplierResponse])
async def create_supplier(
    data: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code = data.code.strip().upper()
    identification_code = (
        data.identification_code.strip() if data.identification_code else None
    )
    await ensure_unique_supplier_fields(
        db, current_user.company_id, code, identification_code
    )
    await validate_supplier_fiscal_position(db, data.fiscal_position_id, current_user.company_id)
    supplier = Supplier(
        company_id=current_user.company_id,
        code=code,
        name=data.name.strip(),
        identification_code=identification_code,
        is_vat_payer=data.is_vat_payer,
        fiscal_position_id=data.fiscal_position_id,
        contact_name=data.contact_name,
        phone=data.phone,
        email=str(data.email) if data.email else None,
        address=data.address,
        bank_account=data.bank_account,
        payment_terms_days=data.payment_terms_days,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(supplier)
    await db.flush()
    await db.refresh(supplier)
    add_supplier_audit(
        db,
        current_user,
        "supplier.created",
        supplier.id,
        {"code": supplier.code, "name": supplier.name},
    )
    resp = SupplierResponse.model_validate(supplier)
    enrich = await _enrich_supplier_response(db, supplier, current_user.company_id)
    for k, v in enrich.items():
        setattr(resp, k, v)
    return ResponseBase(data=resp)


# ── Get / Update / Archive ───────────────────────────────────────────


@router.get("/{supplier_id}", response_model=ResponseBase[SupplierDetailResponse])
async def get_supplier(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = await get_company_supplier(db, supplier_id, current_user.company_id)

    # Eager-load bank details and rating history
    bank_details = (
        await db.execute(
            select(SupplierBankDetail)
            .where(
                SupplierBankDetail.supplier_id == supplier.id,
                SupplierBankDetail.is_active == True,
            )
            .order_by(SupplierBankDetail.is_primary.desc(), SupplierBankDetail.bank_name)
        )
    ).scalars().all()

    rating_history = (
        await db.execute(
            select(SupplierRatingHistory)
            .where(SupplierRatingHistory.supplier_id == supplier.id)
            .order_by(SupplierRatingHistory.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    base = SupplierResponse.model_validate(supplier)
    enrich = await _enrich_supplier_response(db, supplier, current_user.company_id)
    for k, v in enrich.items():
        setattr(base, k, v)

    detail = SupplierDetailResponse(
        **base.model_dump(),
        bank_details=[SupplierBankDetailResponse.model_validate(bd) for bd in bank_details],
        rating_history=[SupplierRatingHistoryResponse.model_validate(rh) for rh in rating_history],
        purchase_orders_url=f"/api/v1/purchase-orders?supplier_id={supplier.id}",
        payables_url=f"/api/v1/supplier-finance/payables?supplier_id={supplier.id}",
    )
    return ResponseBase(data=detail)


@router.patch("/{supplier_id}", response_model=ResponseBase[SupplierResponse])
async def update_supplier(
    supplier_id: UUID,
    data: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = await get_company_supplier(db, supplier_id, current_user.company_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="ცვლილება არ არის მითითებული")

    code = changes.get("code", supplier.code)
    code = code.strip().upper()
    identification_code = changes.get(
        "identification_code", supplier.identification_code
    )
    identification_code = (
        identification_code.strip() if identification_code else None
    )
    await ensure_unique_supplier_fields(
        db,
        current_user.company_id,
        code,
        identification_code,
        exclude_id=supplier.id,
    )
    changes["code"] = code
    if "fiscal_position_id" in changes:
        await validate_supplier_fiscal_position(db, changes["fiscal_position_id"], current_user.company_id)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "identification_code" in changes:
        changes["identification_code"] = identification_code
    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"])

    before = {field: getattr(supplier, field) for field in changes}
    for field, value in changes.items():
        setattr(supplier, field, value)
    await db.flush()
    await db.refresh(supplier)
    add_supplier_audit(
        db,
        current_user,
        "supplier.updated",
        supplier.id,
        {"before": before, "after": changes},
    )
    resp = SupplierResponse.model_validate(supplier)
    enrich = await _enrich_supplier_response(db, supplier, current_user.company_id)
    for k, v in enrich.items():
        setattr(resp, k, v)
    return ResponseBase(data=resp)


@router.post("/{supplier_id}/archive", response_model=ResponseBase[SupplierResponse])
async def archive_supplier(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = await get_company_supplier(db, supplier_id, current_user.company_id)
    supplier.is_active = False
    await db.flush()
    await db.refresh(supplier)
    add_supplier_audit(
        db, current_user, "supplier.archived", supplier.id, {"is_active": False}
    )
    resp = SupplierResponse.model_validate(supplier)
    enrich = await _enrich_supplier_response(db, supplier, current_user.company_id)
    for k, v in enrich.items():
        setattr(resp, k, v)
    return ResponseBase(data=resp)


# ── Duplicate Tax ID Check ───────────────────────────────────────────


@router.get("/check-duplicate-tax-id")
async def check_duplicate_tax_id(
    identification_code: str = Query(..., min_length=1),
    exclude_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if a tax ID (identification_code) is already used by another supplier."""
    query = select(Supplier.id, Supplier.name, Supplier.code).where(
        Supplier.company_id == current_user.company_id,
        Supplier.identification_code == identification_code.strip(),
    )
    if exclude_id:
        query = query.where(Supplier.id != exclude_id)
    result = (await db.execute(query.limit(1))).first()
    if result:
        return ResponseBase(
            data={
                "is_duplicate": True,
                "supplier_id": str(result.id),
                "supplier_name": result.name,
                "supplier_code": result.code,
            }
        )
    return ResponseBase(data={"is_duplicate": False})


# ── Bank Detail Management ───────────────────────────────────────────


@router.get(
    "/{supplier_id}/bank-details",
    response_model=ResponseBase[list[SupplierBankDetailResponse]],
)
async def list_supplier_bank_details(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = await get_company_supplier(db, supplier_id, current_user.company_id)
    bank_details = (
        await db.execute(
            select(SupplierBankDetail)
            .where(
                SupplierBankDetail.supplier_id == supplier.id,
                SupplierBankDetail.is_active == True,
            )
            .order_by(SupplierBankDetail.is_primary.desc(), SupplierBankDetail.bank_name)
        )
    ).scalars().all()
    return ResponseBase(
        data=[SupplierBankDetailResponse.model_validate(bd) for bd in bank_details]
    )


@router.post(
    "/{supplier_id}/bank-details",
    response_model=ResponseBase[SupplierBankDetailResponse],
)
async def create_supplier_bank_detail(
    supplier_id: UUID,
    data: SupplierBankDetailCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = await get_company_supplier(db, supplier_id, current_user.company_id)

    # If this is the first bank detail or marked primary, unset other primaries
    if data.is_primary:
        existing_primary = await db.execute(
            select(SupplierBankDetail).where(
                SupplierBankDetail.supplier_id == supplier.id,
                SupplierBankDetail.is_primary == True,
            )
        )
        for bd in existing_primary.scalars().all():
            bd.is_primary = False

    bank_detail = SupplierBankDetail(
        supplier_id=supplier.id,
        bank_name=data.bank_name.strip(),
        account_name=data.account_name.strip(),
        iban=data.iban.strip(),
        currency=data.currency.strip().upper(),
        is_primary=data.is_primary,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(bank_detail)
    await db.flush()
    await db.refresh(bank_detail)
    add_supplier_audit(
        db,
        current_user,
        "supplier.bank_detail.created",
        supplier.id,
        {"bank_name": bank_detail.bank_name, "iban_masked": "****" + bank_detail.iban[-4:]},
    )
    return ResponseBase(data=SupplierBankDetailResponse.model_validate(bank_detail))


@router.patch(
    "/{supplier_id}/bank-details/{bank_detail_id}",
    response_model=ResponseBase[SupplierBankDetailResponse],
)
async def update_supplier_bank_detail(
    supplier_id: UUID,
    bank_detail_id: UUID,
    data: SupplierBankDetailUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = await get_company_supplier(db, supplier_id, current_user.company_id)
    bank_detail = (
        await db.execute(
            select(SupplierBankDetail).where(
                SupplierBankDetail.id == bank_detail_id,
                SupplierBankDetail.supplier_id == supplier.id,
            )
        )
    ).scalar_one_or_none()
    if not bank_detail:
        raise HTTPException(status_code=404, detail="საბანკო რეკვიზიტი არ მოიძებნა")

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="ცვლილება არ არის მითითებული")

    # Handle primary toggle
    if changes.get("is_primary"):
        existing_primary = await db.execute(
            select(SupplierBankDetail).where(
                SupplierBankDetail.supplier_id == supplier.id,
                SupplierBankDetail.is_primary == True,
                SupplierBankDetail.id != bank_detail.id,
            )
        )
        for bd in existing_primary.scalars().all():
            bd.is_primary = False

    for field, value in changes.items():
        if value is not None and field in ("bank_name", "account_name", "iban"):
            setattr(bank_detail, field, value.strip())
        else:
            setattr(bank_detail, field, value)

    await db.flush()
    await db.refresh(bank_detail)
    add_supplier_audit(
        db,
        current_user,
        "supplier.bank_detail.updated",
        supplier.id,
        {"bank_detail_id": str(bank_detail.id), "changes": list(changes.keys())},
    )
    return ResponseBase(data=SupplierBankDetailResponse.model_validate(bank_detail))


@router.delete(
    "/{supplier_id}/bank-details/{bank_detail_id}",
    response_model=ResponseBase[dict],
)
async def delete_supplier_bank_detail(
    supplier_id: UUID,
    bank_detail_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = await get_company_supplier(db, supplier_id, current_user.company_id)
    bank_detail = (
        await db.execute(
            select(SupplierBankDetail).where(
                SupplierBankDetail.id == bank_detail_id,
                SupplierBankDetail.supplier_id == supplier.id,
            )
        )
    ).scalar_one_or_none()
    if not bank_detail:
        raise HTTPException(status_code=404, detail="საბანკო რეკვიზიტი არ მოიძებნა")

    await db.delete(bank_detail)
    add_supplier_audit(
        db,
        current_user,
        "supplier.bank_detail.deleted",
        supplier.id,
        {"bank_detail_id": str(bank_detail_id)},
    )
    return ResponseBase(data={"deleted": True})


# ── Rating Management ────────────────────────────────────────────────


@router.post(
    "/{supplier_id}/ratings",
    response_model=ResponseBase[SupplierRatingHistoryResponse],
)
async def rate_supplier(
    supplier_id: UUID,
    data: SupplierRatingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = await get_company_supplier(db, supplier_id, current_user.company_id)

    rating_entry = SupplierRatingHistory(
        supplier_id=supplier.id,
        rating=data.rating,
        comment=data.comment,
        changed_by=current_user.id,
    )
    db.add(rating_entry)

    # Update the supplier's current rating
    supplier.rating = data.rating
    await db.flush()
    await db.refresh(rating_entry)

    add_supplier_audit(
        db,
        current_user,
        "supplier.rated",
        supplier.id,
        {"rating": data.rating, "comment": data.comment},
    )
    return ResponseBase(data=SupplierRatingHistoryResponse.model_validate(rating_entry))


@router.get(
    "/{supplier_id}/ratings",
    response_model=ResponseBase[list[SupplierRatingHistoryResponse]],
)
async def list_supplier_ratings(
    supplier_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = await get_company_supplier(db, supplier_id, current_user.company_id)
    ratings = (
        await db.execute(
            select(SupplierRatingHistory)
            .where(SupplierRatingHistory.supplier_id == supplier.id)
            .order_by(SupplierRatingHistory.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return ResponseBase(
        data=[SupplierRatingHistoryResponse.model_validate(r) for r in ratings]
    )


# ── Demo Data Seeding ────────────────────────────────────────────────


@router.post("/seed-demo", response_model=ResponseBase[dict])
async def seed_demo_suppliers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seed demo supplier data for testing and onboarding."""
    existing = (
        await db.execute(
            select(func.count(Supplier.id)).where(
                Supplier.company_id == current_user.company_id
            )
        )
    ).scalar_one()
    if existing > 0:
        raise HTTPException(
            status_code=409,
            detail="კომპანიას უკვე აქვს მომწოდებლები. წაშალეთ არსებული მონაცემები ან გამოიყენეთ სხვა კომპანია.",
        )

    demo_suppliers = [
        {
            "code": "SUP001",
            "name": "შპს თბილისის საკვები პროდუქტები",
            "identification_code": "401234567",
            "is_vat_payer": True,
            "contact_name": "გიორგი მაისურაძე",
            "phone": "+995 599 11 22 33",
            "email": "info@tbilisi-food.ge",
            "address": "თბილისი, დიდუბის რაიონი, აღმაშენებლის გამზ. 15",
            "bank_account": "GE12TB1234567890123456",
            "payment_terms_days": 30,
            "rating": 4.5,
            "notes": "საკვები პროდუქტების მთავარი მომწოდებელი",
        },
        {
            "code": "SUP002",
            "name": "შპს ქართული სამშენებლო მასალები",
            "identification_code": "401234568",
            "is_vat_payer": True,
            "contact_name": "ნინო ბერიძე",
            "phone": "+995 599 22 33 44",
            "email": "sales@construction.ge",
            "address": "თბილისი, საბურთალოს რაიონი, ვაჟა-ფშაველას 45",
            "bank_account": "GE12TB1234567890123457",
            "payment_terms_days": 45,
            "rating": 4.0,
            "notes": "სამშენებლო მასალების მიმწოდებელი",
        },
        {
            "code": "SUP003",
            "name": "აი-სი-ემ საოფისე ტექნიკა",
            "identification_code": "401234569",
            "is_vat_payer": True,
            "contact_name": "დავით ქავთარაძე",
            "phone": "+995 599 33 44 55",
            "email": "info@icm.ge",
            "address": "თბილისი, ვაკის რაიონი, ჭავჭავაძის 32",
            "bank_account": "GE12TB1234567890123458",
            "payment_terms_days": 15,
            "rating": 3.5,
            "notes": "საოფისე ტექნიკისა და კომპიუტერების მომწოდებელი",
        },
        {
            "code": "SUP004",
            "name": "შპს ლოგისტიკური ცენტრი",
            "identification_code": "401234570",
            "is_vat_payer": False,
            "contact_name": "მარიამ ფანცულაია",
            "phone": "+995 599 44 55 66",
            "email": "dispatch@logistics.ge",
            "address": "ქუთაისი, რუსთაველის 12",
            "bank_account": "GE12TB1234567890123459",
            "payment_terms_days": 60,
            "rating": 5.0,
            "notes": "სატრანსპორტო და ლოგისტიკური მომსახურება",
        },
        {
            "code": "SUP005",
            "name": "შპს მწვანე ენერგია",
            "identification_code": "401234571",
            "is_vat_payer": True,
            "contact_name": "თამაზ ნოზაძე",
            "phone": "+995 599 55 66 77",
            "email": "info@greenenergy.ge",
            "address": "ბათუმი, ფერიის ქ. 8",
            "bank_account": "GE12TB1234567890123460",
            "payment_terms_days": 30,
            "rating": 4.0,
            "notes": "ელექტროენერგიისა და განათების მოწყობილობები",
        },
    ]

    created_ids = []
    for s in demo_suppliers:
        supplier = Supplier(
            company_id=current_user.company_id,
            code=s["code"],
            name=s["name"],
            identification_code=s["identification_code"],
            is_vat_payer=s["is_vat_payer"],
            contact_name=s["contact_name"],
            phone=s["phone"],
            email=s["email"],
            address=s["address"],
            bank_account=s["bank_account"],
            payment_terms_days=s["payment_terms_days"],
            notes=s["notes"],
            rating=s["rating"],
            created_by=current_user.id,
        )
        db.add(supplier)
        await db.flush()
        created_ids.append(str(supplier.id))

    await db.flush()
    return ResponseBase(
        data={
            "created_count": len(created_ids),
            "supplier_ids": created_ids,
            "message": "5 დემო მომწოდებელი წარმატებით დაემატა",
        }
    )

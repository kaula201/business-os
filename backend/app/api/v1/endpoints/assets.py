"""Fixed assets API: asset registry, depreciation runs."""
import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.time import utc_now
from app.models.assets import AssetDepreciation, FixedAsset
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.assets import (
    AssetDepreciationResponse,
    DepreciationRunResponse,
    FixedAssetCreate,
    FixedAssetResponse,
    FixedAssetUpdate,
)
from app.schemas.common import ResponseBase
from app.services.accounting_periods import ensure_period_open

router = APIRouter(prefix="/assets", tags=["ძირითადი საშუალებები"])


# ── Helpers ──────────────────────────────────────────────────────────

def add_asset_audit(
    db: AsyncSession,
    current_user: User,
    action: str,
    entity_type: str,
    entity_id: UUID,
    details: dict,
) -> None:
    db.add(
        AuditLog(
            company_id=current_user.company_id,
            user_id=current_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details, ensure_ascii=False, default=str),
        )
    )


async def get_company_asset(
    db: AsyncSession, asset_id: UUID, company_id: UUID
) -> FixedAsset:
    asset = (
        await db.execute(
            select(FixedAsset).where(
                FixedAsset.id == asset_id,
                FixedAsset.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="ძირითადი საშუალება არ მოიძებნა")
    return asset


def calculate_depreciation(asset: FixedAsset) -> Decimal:
    """Calculate monthly depreciation amount."""
    if asset.depreciation_method == "straight_line":
        depreciable_base = asset.purchase_cost - asset.salvage_value
        if depreciable_base <= 0:
            return Decimal("0")
        return (depreciable_base / (asset.useful_life_years * 12)).quantize(Decimal("0.01"))
    elif asset.depreciation_method == "declining":
        rate = Decimal("2") / Decimal(str(asset.useful_life_years))
        monthly_rate = rate / Decimal("12")
        return (asset.book_value * monthly_rate).quantize(Decimal("0.01"))
    return Decimal("0")


# ── CRUD ────────────────────────────────────────────────────────────

@router.get("/", response_model=ResponseBase[list[FixedAssetResponse]])
async def list_assets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FixedAsset)
        .where(FixedAsset.company_id == current_user.company_id)
        .order_by(FixedAsset.name)
    )
    assets = result.scalars().all()
    return ResponseBase(data=assets)


@router.get("/{asset_id}", response_model=ResponseBase[FixedAssetResponse])
async def get_asset(
    asset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await get_company_asset(db, asset_id, current_user.company_id)
    return ResponseBase(data=asset)


@router.post("/", response_model=ResponseBase[FixedAssetResponse], status_code=201)
async def create_asset(
    payload: FixedAssetCreate,
    current_user: User = Depends(require_module("assets", "can_create")),
    db: AsyncSession = Depends(get_db),
):
    await ensure_period_open(db, current_user.company_id, payload.purchase_date)
    asset = FixedAsset(
        company_id=current_user.company_id,
        book_value=payload.purchase_cost,
        **payload.model_dump(),
    )
    db.add(asset)
    await db.flush()
    add_asset_audit(
        db, current_user, "create", "fixed_asset", asset.id,
        {"name": asset.name, "cost": str(asset.purchase_cost), "type": asset.asset_type},
    )
    await db.refresh(asset)
    return ResponseBase(data=asset, message="ძირითადი საშუალება დამატებულია")


@router.put("/{asset_id}", response_model=ResponseBase[FixedAssetResponse])
async def update_asset(
    asset_id: UUID,
    payload: FixedAssetUpdate,
    current_user: User = Depends(require_module("assets", "can_edit")),
    db: AsyncSession = Depends(get_db),
):
    asset = await get_company_asset(db, asset_id, current_user.company_id)
    await ensure_period_open(db, current_user.company_id, asset.purchase_date)
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="განახლების მონაცემები არ არის მოწოდებული")
    for key, value in update_data.items():
        setattr(asset, key, value)
    await db.flush()
    add_asset_audit(
        db, current_user, "update", "fixed_asset", asset.id,
        {"updated_fields": list(update_data.keys())},
    )
    await db.refresh(asset)
    return ResponseBase(data=asset, message="ძირითადი საშუალება განახლებულია")


@router.delete("/{asset_id}", response_model=ResponseBase)
async def delete_asset(
    asset_id: UUID,
    current_user: User = Depends(require_module("assets", "can_edit")),
    db: AsyncSession = Depends(get_db),
):
    asset = await get_company_asset(db, asset_id, current_user.company_id)
    await ensure_period_open(db, current_user.company_id, asset.purchase_date)
    has_depreciation = await db.scalar(
        select(AssetDepreciation.id).where(
            AssetDepreciation.asset_id == asset_id,
            AssetDepreciation.company_id == current_user.company_id,
        ).limit(1)
    )
    if has_depreciation:
        raise HTTPException(
            status_code=409,
            detail="ამორტიზაციის ისტორიის მქონე აქტივის წაშლა არ შეიძლება; შეცვალეთ სტატუსი",
        )
    await db.delete(asset)
    add_asset_audit(
        db, current_user, "delete", "fixed_asset", asset_id,
        {"name": asset.name},
    )
    return ResponseBase(message="ძირითადი საშუალება წაშლილია")


# ── Depreciation ────────────────────────────────────────────────────

@router.post("/{asset_id}/run-depreciation", response_model=ResponseBase[DepreciationRunResponse])
async def run_depreciation(
    asset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Calculate and record one month of depreciation."""
    if current_user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="ამორტიზაციის დარიცხვის უფლება არ გაქვთ")

    asset = await get_company_asset(db, asset_id, current_user.company_id)

    if asset.status == "disposed":
        raise HTTPException(status_code=400, detail="ჩამოწერილი აქტივის ამორტიზაცია შეუძლებელია")
    if asset.status == "fully_depreciated":
        raise HTTPException(status_code=400, detail="აქტივი უკვე სრულად ამორტიზებულია")

    amount = calculate_depreciation(asset)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="ამორტიზაციის თანხა ნულის ტოლია")

    now = utc_now()
    await ensure_period_open(db, current_user.company_id, now.date())
    period_label = f"{now.year}-{now.month:02d}"

    # Record depreciation
    dep = AssetDepreciation(
        company_id=current_user.company_id,
        asset_id=asset_id,
        depreciation_date=now.date(),
        amount=amount,
        period_label=period_label,
    )
    db.add(dep)

    # Update asset
    asset.accumulated_depreciation += amount
    asset.book_value = asset.purchase_cost - asset.accumulated_depreciation
    asset.last_depreciation_date = now.date()

    if asset.book_value <= 0:
        asset.book_value = Decimal("0")
        asset.status = "fully_depreciated"

    await db.flush()
    add_asset_audit(
        db, current_user, "depreciation", "fixed_asset", asset.id,
        {"amount": str(amount), "period": period_label, "new_book_value": str(asset.book_value)},
    )

    result = DepreciationRunResponse(
        asset_id=asset.id,
        asset_name=asset.name,
        depreciation_amount=float(amount),
        new_book_value=float(asset.book_value),
        new_accumulated_depreciation=float(asset.accumulated_depreciation),
        is_fully_depreciated=asset.status == "fully_depreciated",
    )
    return ResponseBase(data=result, message=f"ამორტიზაცია დაფიქსირებულია: {float(amount)} ₾")


@router.get("/{asset_id}/depreciation-history", response_model=ResponseBase[list[AssetDepreciationResponse]])
async def depreciation_history(
    asset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_company_asset(db, asset_id, current_user.company_id)
    result = await db.execute(
        select(AssetDepreciation)
        .where(
            AssetDepreciation.asset_id == asset_id,
            AssetDepreciation.company_id == current_user.company_id,
        )
        .order_by(AssetDepreciation.depreciation_date.desc())
    )
    entries = result.scalars().all()
    return ResponseBase(data=entries)

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.contract import Contract
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.contract import ContractCreate, ContractResponse, ContractUpdate

router = APIRouter(prefix="/contracts", tags=["Contracts"])


@router.get("/", response_model=ResponseBase[PaginatedResponse[ContractResponse]])
async def list_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("contracts", "can_access")),
):
    query = select(Contract).where(Contract.company_id == current_user.company_id)
    if status:
        query = query.where(Contract.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = (
        query.order_by(Contract.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    contracts = (await db.execute(query)).scalars().all()

    return ResponseBase(
        data=PaginatedResponse(
            items=[ContractResponse.model_validate(c) for c in contracts],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )
    )


@router.get("/{contract_id}", response_model=ResponseBase[ContractResponse])
async def get_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("contracts", "can_access")),
):
    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.company_id == current_user.company_id,
        )
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="კონტრაქტი არ მოიძებნა")
    return ResponseBase(data=ContractResponse.model_validate(contract))


@router.post("/", response_model=ResponseBase[ContractResponse])
async def create_contract(
    data: ContractCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("contracts", "can_create")),
):
    contract = Contract(
        company_id=current_user.company_id,
        title=data.title,
        counterparty=data.counterparty,
        start_date=data.start_date,
        end_date=data.end_date,
        value=data.value,
        status=data.status,
        notes=data.notes,
    )
    db.add(contract)
    await db.flush()
    await db.refresh(contract)
    return ResponseBase(data=ContractResponse.model_validate(contract))


@router.patch("/{contract_id}", response_model=ResponseBase[ContractResponse])
async def update_contract(
    contract_id: UUID,
    data: ContractUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("contracts", "can_edit")),
):
    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.company_id == current_user.company_id,
        )
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="კონტრაქტი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contract, field, value)

    await db.flush()
    await db.refresh(contract)
    return ResponseBase(data=ContractResponse.model_validate(contract))


@router.delete("/{contract_id}", response_model=ResponseBase[dict])
async def delete_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("contracts", "can_delete")),
):
    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.company_id == current_user.company_id,
        )
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="კონტრაქტი არ მოიძებნა")

    await db.delete(contract)
    await db.flush()
    return ResponseBase(data={"message": "კონტრაქტი წაიშალა"})

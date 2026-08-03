import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.audit import AuditLog
from app.models.purchase import PurchaseApprovalPolicy
from app.models.user import User
from app.schemas.common import ResponseBase
from app.schemas.purchase_approval import (
    PurchaseApprovalPolicyResponse,
    PurchaseApprovalPolicyUpdate,
)

router = APIRouter(prefix="/purchase-approval-policy", tags=["შესყიდვის დამტკიცება"])
DEFAULT_MANAGER_APPROVAL_LIMIT = Decimal("5000.00")


def response_for(policy: PurchaseApprovalPolicy | None) -> PurchaseApprovalPolicyResponse:
    if policy is None:
        return PurchaseApprovalPolicyResponse(
            manager_approval_limit=float(DEFAULT_MANAGER_APPROVAL_LIMIT),
        )
    return PurchaseApprovalPolicyResponse(
        manager_approval_limit=float(policy.manager_approval_limit),
        updated_by=policy.updated_by,
        updated_at=policy.updated_at,
    )


@router.get("/", response_model=ResponseBase[PurchaseApprovalPolicyResponse])
async def get_purchase_approval_policy(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    policy = (
        await db.execute(
            select(PurchaseApprovalPolicy).where(
                PurchaseApprovalPolicy.company_id == current_user.company_id
            )
        )
    ).scalar_one_or_none()
    return ResponseBase(data=response_for(policy))


@router.patch("/", response_model=ResponseBase[PurchaseApprovalPolicyResponse])
async def update_purchase_approval_policy(
    data: PurchaseApprovalPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != User.Role.ADMIN:
        raise HTTPException(status_code=403, detail="approval policy-ის შეცვლა მხოლოდ admin-ს შეუძლია")

    policy = (
        await db.execute(
            select(PurchaseApprovalPolicy)
            .where(PurchaseApprovalPolicy.company_id == current_user.company_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    previous = DEFAULT_MANAGER_APPROVAL_LIMIT if policy is None else policy.manager_approval_limit
    if policy is None:
        policy = PurchaseApprovalPolicy(
            company_id=current_user.company_id,
            manager_approval_limit=data.manager_approval_limit,
            updated_by=current_user.id,
        )
        db.add(policy)
    else:
        policy.manager_approval_limit = data.manager_approval_limit
        policy.updated_by = current_user.id
    await db.flush()
    await db.refresh(policy)
    db.add(AuditLog(
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="purchase_approval_policy.updated",
        entity_type="purchase_approval_policy",
        entity_id=policy.id,
        details=json.dumps({
            "previous_manager_approval_limit": str(previous),
            "manager_approval_limit": str(data.manager_approval_limit),
        }),
    ))
    return ResponseBase(data=response_for(policy))

"""Approvals API: generic approval workflow requests."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.approval import ApprovalRequest
from app.models.user import User
from app.schemas.approval import (
    ApprovalApprove,
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    ApprovalRequestUpdate,
)
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/approvals", tags=["Approvals"])

ALLOWED_STATUSES = ApprovalRequest.Status.CHOICES


async def _get_owned_request(
    db: AsyncSession, request_id: UUID, company_id: UUID
) -> ApprovalRequest:
    req = await db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.id == request_id,
            ApprovalRequest.company_id == company_id,
        )
    )
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return req


def _to_response(req: ApprovalRequest) -> ApprovalRequestResponse:
    return ApprovalRequestResponse(
        id=req.id,
        company_id=req.company_id,
        title=req.title,
        description=req.description,
        approval_type=req.approval_type,
        amount=float(req.amount) if req.amount is not None else None,
        status=req.status,
        requested_by=req.requested_by,
        requested_by_name=req.requester.full_name if req.requester else None,
        approved_by=req.approved_by,
        approved_by_name=req.approver.full_name if req.approver else None,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


@router.get("/", response_model=ResponseBase[list[ApprovalRequestResponse]])
async def list_approvals(
    status: str | None = Query(default=None),
    current_user: User = Depends(require_module("approvals", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    if status and status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {ALLOWED_STATUSES}")

    query = select(ApprovalRequest).where(
        ApprovalRequest.company_id == current_user.company_id
    )
    if status:
        query = query.where(ApprovalRequest.status == status)
    query = query.order_by(ApprovalRequest.created_at.desc())

    result = await db.execute(query)
    return ResponseBase(data=[_to_response(r) for r in result.scalars().all()])


@router.get("/{request_id}", response_model=ResponseBase[ApprovalRequestResponse])
async def get_approval(
    request_id: UUID,
    current_user: User = Depends(require_module("approvals", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    req = await _get_owned_request(db, request_id, current_user.company_id)
    return ResponseBase(data=_to_response(req))


@router.post("/", response_model=ResponseBase[ApprovalRequestResponse], status_code=201)
async def create_approval(
    payload: ApprovalRequestCreate,
    current_user: User = Depends(require_module("approvals", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    req = ApprovalRequest(
        company_id=current_user.company_id,
        requested_by=current_user.id,
        status=ApprovalRequest.Status.PENDING,
        **payload.model_dump(),
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return ResponseBase(data=_to_response(req), message="Approval request created")


@router.patch("/{request_id}", response_model=ResponseBase[ApprovalRequestResponse])
async def update_approval(
    request_id: UUID,
    payload: ApprovalRequestUpdate,
    current_user: User = Depends(require_module("approvals", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    req = await _get_owned_request(db, request_id, current_user.company_id)
    if req.status != ApprovalRequest.Status.PENDING:
        raise HTTPException(status_code=400, detail="Only pending requests can be edited")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(req, field, value)
    await db.commit()
    await db.refresh(req)
    return ResponseBase(data=_to_response(req), message="Approval request updated")


@router.delete("/{request_id}", response_model=ResponseBase[ApprovalRequestResponse])
async def delete_approval(
    request_id: UUID,
    current_user: User = Depends(require_module("approvals", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    req = await _get_owned_request(db, request_id, current_user.company_id)
    await db.delete(req)
    await db.commit()
    return ResponseBase(message="Approval request deleted")


@router.patch("/{request_id}/approve", response_model=ResponseBase[ApprovalRequestResponse])
async def approve_approval(
    request_id: UUID,
    payload: ApprovalApprove,
    current_user: User = Depends(require_module("approvals", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    req = await _get_owned_request(db, request_id, current_user.company_id)
    if req.status != ApprovalRequest.Status.PENDING:
        raise HTTPException(status_code=400, detail=f"Cannot change status from '{req.status}'")

    req.status = (
        ApprovalRequest.Status.APPROVED
        if payload.action == "approve"
        else ApprovalRequest.Status.REJECTED
    )
    req.approved_by = current_user.id
    await db.commit()
    await db.refresh(req)
    return ResponseBase(
        data=_to_response(req),
        message="Approval request approved" if payload.action == "approve" else "Approval request rejected",
    )

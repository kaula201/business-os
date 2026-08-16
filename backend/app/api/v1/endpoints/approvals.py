"""Approvals API: generic approval workflow requests."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.core.time import utc_now
from app.models.approval import ApprovalRequest
from app.models.security import ApprovalStep
from app.models.user import User
from app.schemas.approval import (
    ApprovalApprove,
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    ApprovalRequestUpdate,
)
from app.schemas.common import ResponseBase, PaginatedResponse

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


@router.get("/", response_model=ResponseBase[PaginatedResponse[ApprovalRequestResponse]])
async def list_approvals(
    status: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
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

    total = (
        await db.execute(
            select(func.count()).select_from(query.subquery())
        )
    ).scalar() or 0
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return ResponseBase(data=PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_response(r) for r in result.scalars().all()],
    ))


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


# ── Multi-level approval steps ────────────────────────────────────────────────

@router.get("/{request_id}/steps", response_model=ResponseBase[list[dict]])
async def list_approval_steps(
    request_id: UUID,
    current_user: User = Depends(require_module("approvals", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_request(db, request_id, current_user.company_id)
    rows = (await db.execute(
        select(ApprovalStep).where(ApprovalStep.approval_id == request_id).order_by(ApprovalStep.step_order)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(s.id), "step_order": s.step_order, "approver_id": str(s.approver_id) if s.approver_id else None,
        "role_required": s.role_required, "status": s.status, "comment": s.comment,
        "decided_at": s.decided_at.isoformat() if s.decided_at else None,
    } for s in rows])


@router.post("/{request_id}/steps", response_model=ResponseBase[dict], status_code=201)
async def add_approval_step(
    request_id: UUID,
    payload: dict,
    current_user: User = Depends(require_module("approvals", "can_create")),
    db: AsyncSession = Depends(get_db),
):
    req = await _get_owned_request(db, request_id, current_user.company_id)
    if req.status != ApprovalRequest.Status.PENDING:
        raise HTTPException(status_code=400, detail="Only pending requests can have steps added")

    step = ApprovalStep(
        company_id=current_user.company_id,
        approval_id=request_id,
        step_order=int(payload.get("step_order", 1)),
        approver_id=payload.get("approver_id"),
        role_required=payload.get("role_required"),
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return ResponseBase(data={"id": str(step.id), "step_order": step.step_order}, message="Approval step added")


@router.patch("/steps/{step_id}/decide", response_model=ResponseBase[dict])
async def decide_approval_step(
    step_id: UUID,
    payload: dict,
    current_user: User = Depends(require_module("approvals", "can_access")),
    db: AsyncSession = Depends(get_db),
):
    step = await db.scalar(
        select(ApprovalStep).where(
            ApprovalStep.id == step_id,
            ApprovalStep.company_id == current_user.company_id,
        )
    )
    if not step:
        raise HTTPException(status_code=404, detail="Approval step not found")
    if step.status != "pending":
        raise HTTPException(status_code=400, detail="Step already decided")

    action = payload.get("action", "approve")
    step.status = "approved" if action == "approve" else "rejected"
    step.comment = payload.get("comment")
    step.decided_at = utc_now()
    await db.commit()

    # If all steps approved → approve the request; any rejection → reject
    req = await _get_owned_request(db, step.approval_id, current_user.company_id)
    steps = (await db.execute(
        select(ApprovalStep).where(ApprovalStep.approval_id == step.approval_id)
    )).scalars().all()
    if any(s.status == "rejected" for s in steps):
        req.status = ApprovalRequest.Status.REJECTED
    elif all(s.status == "approved" for s in steps):
        req.status = ApprovalRequest.Status.APPROVED
        req.approved_by = current_user.id
    await db.commit()

    return ResponseBase(data={"id": str(step.id), "status": step.status}, message="Step decided")

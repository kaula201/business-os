from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.recruitment import JobPosting
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.recruitment import (
    JobPostingCreate,
    JobPostingResponse,
    JobPostingUpdate,
)

router = APIRouter(prefix="/recruitment", tags=["Recruitment"])


@router.get("/", response_model=ResponseBase[PaginatedResponse[JobPostingResponse]])
async def list_job_postings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("recruitment", "can_access")),
):
    query = select(JobPosting).where(
        JobPosting.company_id == current_user.company_id
    )
    if status:
        query = query.where(JobPosting.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = (
        query.order_by(JobPosting.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    postings = (await db.execute(query)).scalars().all()

    return ResponseBase(
        data=PaginatedResponse(
            items=[JobPostingResponse.model_validate(p) for p in postings],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )
    )


@router.get("/{job_posting_id}", response_model=ResponseBase[JobPostingResponse])
async def get_job_posting(
    job_posting_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("recruitment", "can_access")),
):
    result = await db.execute(
        select(JobPosting).where(
            JobPosting.id == job_posting_id,
            JobPosting.company_id == current_user.company_id,
        )
    )
    posting = result.scalar_one_or_none()
    if not posting:
        raise HTTPException(status_code=404, detail="ვაკანსია არ მოიძებნა")
    return ResponseBase(data=JobPostingResponse.model_validate(posting))


@router.post("/", response_model=ResponseBase[JobPostingResponse])
async def create_job_posting(
    data: JobPostingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("recruitment", "can_create")),
):
    posting = JobPosting(
        company_id=current_user.company_id,
        title=data.title,
        department=data.department,
        location=data.location,
        employment_type=data.employment_type,
        salary_min=data.salary_min,
        salary_max=data.salary_max,
        description=data.description,
        status=data.status,
    )
    db.add(posting)
    await db.flush()
    await db.refresh(posting)
    return ResponseBase(data=JobPostingResponse.model_validate(posting))


@router.patch("/{job_posting_id}", response_model=ResponseBase[JobPostingResponse])
async def update_job_posting(
    job_posting_id: UUID,
    data: JobPostingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("recruitment", "can_edit")),
):
    result = await db.execute(
        select(JobPosting).where(
            JobPosting.id == job_posting_id,
            JobPosting.company_id == current_user.company_id,
        )
    )
    posting = result.scalar_one_or_none()
    if not posting:
        raise HTTPException(status_code=404, detail="ვაკანსია არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(posting, field, value)

    await db.flush()
    await db.refresh(posting)
    return ResponseBase(data=JobPostingResponse.model_validate(posting))


@router.delete("/{job_posting_id}", response_model=ResponseBase[dict])
async def delete_job_posting(
    job_posting_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("recruitment", "can_delete")),
):
    result = await db.execute(
        select(JobPosting).where(
            JobPosting.id == job_posting_id,
            JobPosting.company_id == current_user.company_id,
        )
    )
    posting = result.scalar_one_or_none()
    if not posting:
        raise HTTPException(status_code=404, detail="ვაკანსია არ მოიძებნა")

    await db.delete(posting)
    await db.flush()
    return ResponseBase(data={"message": "ვაკანსია წაიშალა"})

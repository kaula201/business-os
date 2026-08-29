"""Projects API — enhanced with milestones, owner, progress, profitability, budget integration."""
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.projects import Project, ProjectMember, ProjectMilestone, ProjectTemplate, ProjectTemplateMilestone, ProjectTemplateTask, ProjectTimesheet
from app.models.task import Task
from app.models.budgeting import BudgetPlan
from app.schemas.common import ResponseBase, PaginatedResponse
from app.schemas.projects import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectDetailResponse,
    MilestoneCreate, MilestoneUpdate, MilestoneResponse,
)
from datetime import date, datetime
from typing import Optional

router = APIRouter(prefix="/projects", tags=["პროექტები"])


# ═══════════════════════════════════════════════════════════════════════════════
# Project Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=ResponseBase[PaginatedResponse[ProjectResponse]])
async def list_projects(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    search: str | None = None,
    manager_id: UUID | None = None,
    owner_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_access")),
):
    query = (
        select(Project)
        .where(Project.company_id == current_user.company_id)
        .options(selectinload(Project.manager), selectinload(Project.owner), selectinload(Project.budget_plan))
    )
    if status:
        query = query.where(Project.status == status)
    if search:
        query = query.where(
            Project.name.ilike(f"%{search}%") | Project.code.ilike(f"%{search}%")
        )
    if manager_id:
        query = query.where(Project.manager_id == manager_id)
    if owner_id:
        query = query.where(Project.owner_id == owner_id)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    projects = result.scalars().all()

    items = []
    for p in projects:
        resp = ProjectResponse.model_validate(p)
        resp.manager_name = p.manager.full_name if p.manager else None
        resp.owner_name = p.owner.full_name if p.owner else None
        resp.budget_plan_name = p.budget_plan.name if p.budget_plan else None
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# Project Templates (Odoo-style) — must be declared BEFORE /{project_id} routes
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/templates", response_model=ResponseBase[list[dict]])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_access")),
):
    rows = (await db.execute(
        select(ProjectTemplate).where(ProjectTemplate.company_id == current_user.company_id)
        .options(selectinload(ProjectTemplate.milestones).selectinload(ProjectTemplateMilestone.tasks))
        .order_by(ProjectTemplate.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(t.id), "name": t.name, "description": t.description,
        "default_budget": float(t.default_budget),
        "milestones": [{
            "id": str(m.id), "name": m.name, "description": m.description, "sort_order": m.sort_order,
            "tasks": [{
                "id": str(tt.id), "title": tt.title, "description": tt.description,
                "priority": tt.priority, "sort_order": tt.sort_order,
            } for tt in m.tasks],
        } for m in t.milestones],
    } for t in rows])


@router.post("/templates", response_model=ResponseBase[dict], status_code=201)
async def create_template(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_create")),
):
    """Create a template: {"name": "...", "description": "...", "default_budget": 0,
    "milestones": [{"name": "...", "tasks": [{"title": "...", "priority": "medium"}]}]}"""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="შაბლონის სახელი სავალდებულოა")
    template = ProjectTemplate(
        company_id=current_user.company_id, name=name,
        description=payload.get("description"),
        default_budget=Decimal(str(payload.get("default_budget") or 0)),
        created_by=current_user.id,
    )
    db.add(template)
    await db.flush()
    for i, ms in enumerate(payload.get("milestones", [])):
        milestone = ProjectTemplateMilestone(
            template_id=template.id, name=ms.get("name", f"ეტაპი {i + 1}"),
            description=ms.get("description"), sort_order=i,
        )
        db.add(milestone)
        await db.flush()
        for j, tk in enumerate(ms.get("tasks", [])):
            db.add(ProjectTemplateTask(
                template_id=template.id, milestone_id=milestone.id,
                title=tk.get("title", ""), description=tk.get("description"),
                priority=tk.get("priority", "medium"), sort_order=j,
            ))
    await db.flush()
    return ResponseBase(data={"id": str(template.id), "name": template.name}, message="შაბლონი შეიქმნა")


@router.post("/templates/{template_id}/instantiate", response_model=ResponseBase[dict], status_code=201)
async def instantiate_template(
    template_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_create")),
):
    """Create a project from a template — copies milestones + tasks (Odoo-style)."""
    template = (await db.execute(
        select(ProjectTemplate).where(ProjectTemplate.id == template_id, ProjectTemplate.company_id == current_user.company_id)
        .options(selectinload(ProjectTemplate.milestones).selectinload(ProjectTemplateMilestone.tasks))
    )).unique().scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="შაბლონი არ მოიძებნა")

    code = (payload.get("code") or "").strip() or f"PRJ-{template.name[:4].upper()}"
    proj = Project(
        company_id=current_user.company_id, code=code,
        name=payload.get("name") or template.name,
        description=payload.get("description") or template.description,
        manager_id=payload.get("manager_id"),
        status="draft",
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
        budget_amount=Decimal(str(payload.get("budget_amount") if payload.get("budget_amount") is not None else template.default_budget)),
    )
    db.add(proj)
    await db.flush()

    milestone_map: dict[str, ProjectMilestone] = {}
    for ms in template.milestones:
        milestone = ProjectMilestone(
            project_id=proj.id, name=ms.name, description=ms.description,
            sort_order=ms.sort_order, status="pending",
        )
        db.add(milestone)
        await db.flush()
        milestone_map[str(ms.id)] = milestone
        for tk in ms.tasks:
            db.add(Task(
                company_id=current_user.company_id, project_id=proj.id,
                title=tk.title, description=tk.description,
                priority=tk.priority, status="todo",
                created_by=current_user.id,
            ))
    await db.flush()
    return ResponseBase(data={
        "id": str(proj.id), "code": proj.code, "name": proj.name,
        "milestones_created": len(milestone_map),
    }, message="პროექტი შეიქმნა შაბლონიდან")


@router.delete("/templates/{template_id}", response_model=ResponseBase)
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_create")),
):
    template = (await db.execute(
        select(ProjectTemplate).where(ProjectTemplate.id == template_id, ProjectTemplate.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="შაბლონი არ მოიძებნა")
    await db.delete(template)
    return ResponseBase(message="შაბლონი წაიშალა")


@router.post("/", response_model=ResponseBase[ProjectResponse], status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_create")),
):
    proj = Project(company_id=current_user.company_id, **data.model_dump())
    db.add(proj)
    await db.flush()
    await db.refresh(proj, ["manager", "owner", "budget_plan"])
    resp = ProjectResponse.model_validate(proj)
    resp.manager_name = proj.manager.full_name if proj.manager else None
    resp.owner_name = proj.owner.full_name if proj.owner else None
    resp.budget_plan_name = proj.budget_plan.name if proj.budget_plan else None
    return ResponseBase(data=resp)


@router.get("/{project_id}", response_model=ResponseBase[ProjectDetailResponse])
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_access")),
):
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.company_id == current_user.company_id)
        .options(
            selectinload(Project.manager),
            selectinload(Project.owner),
            selectinload(Project.budget_plan),
            selectinload(Project.milestones),
            selectinload(Project.tasks),
        )
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="პროექტი არ მოიძებნა")

    resp = ProjectDetailResponse.model_validate(proj)
    resp.manager_name = proj.manager.full_name if proj.manager else None
    resp.owner_name = proj.owner.full_name if proj.owner else None
    resp.budget_plan_name = proj.budget_plan.name if proj.budget_plan else None

    # Milestones
    resp.milestones = []
    for m in sorted(proj.milestones, key=lambda x: x.sort_order):
        ms = MilestoneResponse.model_validate(m)
        ms.owner_name = m.owner.full_name if m.owner else None
        resp.milestones.append(ms)

    # Task counts
    all_tasks = proj.tasks
    resp.task_count = len(all_tasks)
    resp.completed_task_count = sum(1 for t in all_tasks if t.status == "done")

    # Profitability
    resp.profitability = proj.budget_amount - proj.spent_amount
    if proj.budget_amount and proj.budget_amount > 0:
        resp.profitability_percent = (resp.profitability / proj.budget_amount * 100).quantize(Decimal("0.01"))

    return ResponseBase(data=resp)


@router.patch("/{project_id}", response_model=ResponseBase[ProjectResponse])
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_create")),
):
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.company_id == current_user.company_id)
        .options(selectinload(Project.manager), selectinload(Project.owner), selectinload(Project.budget_plan))
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="პროექტი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(proj, field, value)

    await db.flush()
    await db.refresh(proj)
    resp = ProjectResponse.model_validate(proj)
    resp.manager_name = proj.manager.full_name if proj.manager else None
    resp.owner_name = proj.owner.full_name if proj.owner else None
    resp.budget_plan_name = proj.budget_plan.name if proj.budget_plan else None
    return ResponseBase(data=resp)


@router.delete("/{project_id}", response_model=ResponseBase)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_create")),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == current_user.company_id)
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="პროექტი არ მოიძებნა")
    await db.delete(proj)
    return ResponseBase(message="პროექტი წაიშალა")


# ═══════════════════════════════════════════════════════════════════════════════
# Milestone Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{project_id}/milestones", response_model=ResponseBase[list[MilestoneResponse]])
async def list_milestones(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_access")),
):
    # Verify project exists and belongs to company
    proj_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == current_user.company_id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="პროექტი არ მოიძებნა")

    result = await db.execute(
        select(ProjectMilestone)
        .where(ProjectMilestone.project_id == project_id)
        .order_by(ProjectMilestone.sort_order, ProjectMilestone.created_at)
    )
    milestones = result.scalars().all()
    items = []
    for m in milestones:
        resp = MilestoneResponse.model_validate(m)
        resp.owner_name = m.owner.full_name if m.owner else None
        items.append(resp)
    return ResponseBase(data=items)


@router.post("/{project_id}/milestones", response_model=ResponseBase[MilestoneResponse], status_code=201)
async def create_milestone(
    project_id: UUID,
    data: MilestoneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_create")),
):
    proj_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == current_user.company_id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="პროექტი არ მოიძებნა")

    milestone = ProjectMilestone(project_id=project_id, **data.model_dump())
    db.add(milestone)
    await db.flush()
    await db.refresh(milestone, ["owner"])
    resp = MilestoneResponse.model_validate(milestone)
    resp.owner_name = milestone.owner.full_name if milestone.owner else None
    return ResponseBase(data=resp)


@router.patch("/{project_id}/milestones/{milestone_id}", response_model=ResponseBase[MilestoneResponse])
async def update_milestone(
    project_id: UUID,
    milestone_id: UUID,
    data: MilestoneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_create")),
):
    result = await db.execute(
        select(ProjectMilestone)
        .where(ProjectMilestone.id == milestone_id, ProjectMilestone.project_id == project_id)
        .options(selectinload(ProjectMilestone.owner))
    )
    milestone = result.scalar_one_or_none()
    if not milestone:
        raise HTTPException(status_code=404, detail="ეტაპი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(milestone, field, value)

    # Auto-set completed_date when status changes to completed
    if data.status == ProjectMilestone.Status.COMPLETED and not milestone.completed_date:
        milestone.completed_date = date.today()
    # Auto-set completion_percent to 100 when completed
    if data.status == ProjectMilestone.Status.COMPLETED:
        milestone.completion_percent = Decimal("100")

    await db.flush()
    await db.refresh(milestone, ["owner"])
    resp = MilestoneResponse.model_validate(milestone)
    resp.owner_name = milestone.owner.full_name if milestone.owner else None
    return ResponseBase(data=resp)


@router.delete("/{project_id}/milestones/{milestone_id}", response_model=ResponseBase)
async def delete_milestone(
    project_id: UUID,
    milestone_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_create")),
):
    result = await db.execute(
        select(ProjectMilestone).where(
            ProjectMilestone.id == milestone_id,
            ProjectMilestone.project_id == project_id,
        )
    )
    milestone = result.scalar_one_or_none()
    if not milestone:
        raise HTTPException(status_code=404, detail="ეტაპი არ მოიძებნა")
    await db.delete(milestone)
    return ResponseBase(message="ეტაპი წაიშალა")


# ═══════════════════════════════════════════════════════════════════════════════
# Progress & Profitability Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{project_id}/progress", response_model=ResponseBase)
async def get_project_progress(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_access")),
):
    """Get detailed progress breakdown for a project."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.company_id == current_user.company_id)
        .options(selectinload(Project.tasks), selectinload(Project.milestones))
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="პროექტი არ მოიძებნა")

    all_tasks = proj.tasks
    total_tasks = len(all_tasks)
    completed_tasks = sum(1 for t in all_tasks if t.status == "done")
    in_progress_tasks = sum(1 for t in all_tasks if t.status == "in_progress")
    todo_tasks = sum(1 for t in all_tasks if t.status == "todo")

    all_milestones = proj.milestones
    total_milestones = len(all_milestones)
    completed_milestones = sum(1 for m in all_milestones if m.status == "completed")

    return ResponseBase(data={
        "completion_percent": float(proj.completion_percent),
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "in_progress": in_progress_tasks,
            "todo": todo_tasks,
            "completion_percent": round(completed_tasks / total_tasks * 100, 2) if total_tasks > 0 else 0,
        },
        "milestones": {
            "total": total_milestones,
            "completed": completed_milestones,
            "completion_percent": round(completed_milestones / total_milestones * 100, 2) if total_milestones > 0 else 0,
        },
    })


@router.get("/{project_id}/profitability", response_model=ResponseBase)
async def get_project_profitability(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_access")),
):
    """Get profitability analysis for a project."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.company_id == current_user.company_id)
        .options(selectinload(Project.budget_plan))
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="პროექტი არ მოიძებნა")

    budget = proj.budget_amount
    spent = proj.spent_amount
    revenue = proj.revenue_amount
    profit = revenue - spent
    margin_pct = (profit / revenue * 100).quantize(Decimal("0.01")) if revenue and revenue > 0 else Decimal("0")
    budget_remaining = budget - spent

    return ResponseBase(data={
        "budget_amount": float(budget),
        "spent_amount": float(spent),
        "revenue_amount": float(revenue),
        "profitability": float(profit),
        "profitability_percent": float(margin_pct),
        "budget_remaining": float(budget_remaining),
        "budget_plan_id": str(proj.budget_plan_id) if proj.budget_plan_id else None,
        "budget_plan_name": proj.budget_plan.name if proj.budget_plan else None,
    })


# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════ Resource planning — project members ═══════════════════

@router.get("/{project_id}/members", response_model=ResponseBase[list[dict]])
async def list_project_members(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_access")),
):
    rows = (await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.company_id == current_user.company_id,
        ).options(selectinload(ProjectMember.user))
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(m.id), "project_id": str(m.project_id), "user_id": str(m.user_id),
        "user_name": m.user.full_name if m.user else None,
        "role": m.role, "allocation_percent": float(m.allocation_percent),
        "start_date": m.start_date.isoformat() if m.start_date else None,
        "end_date": m.end_date.isoformat() if m.end_date else None,
        "hourly_rate": float(m.hourly_rate),
    } for m in rows])


@router.post("/{project_id}/members", response_model=ResponseBase[dict], status_code=201)
async def add_project_member(
    project_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_edit")),
):
    proj = (await db.execute(select(Project).where(
        Project.id == project_id, Project.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="პროექტი არ მოიძებნა")
    member = ProjectMember(
        company_id=current_user.company_id, project_id=project_id,
        user_id=data["user_id"],
        role=data.get("role", "member"),
        allocation_percent=Decimal(str(data.get("allocation_percent", 100))),
        start_date=date.fromisoformat(data["start_date"]) if data.get("start_date") else None,
        end_date=date.fromisoformat(data["end_date"]) if data.get("end_date") else None,
        hourly_rate=Decimal(str(data.get("hourly_rate", 0))),
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return ResponseBase(data={"id": str(member.id)}, message="წევრი დაემატა")


@router.patch("/members/{member_id}", response_model=ResponseBase[dict])
async def update_project_member(
    member_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_edit")),
):
    member = (await db.execute(select(ProjectMember).where(
        ProjectMember.id == member_id, ProjectMember.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="წევრი არ მოიძებნა")
    if "role" in data:
        member.role = data["role"]
    if "allocation_percent" in data:
        member.allocation_percent = Decimal(str(data["allocation_percent"]))
    if "hourly_rate" in data:
        member.hourly_rate = Decimal(str(data["hourly_rate"]))
    if "end_date" in data:
        member.end_date = data["end_date"]
    await db.commit()
    return ResponseBase(data={"id": str(member_id)}, message="წევრი განახლდა")


@router.delete("/members/{member_id}", response_model=ResponseBase[dict])
async def remove_project_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_edit")),
):
    member = (await db.execute(select(ProjectMember).where(
        ProjectMember.id == member_id, ProjectMember.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="წევრი არ მოიძებნა")
    await db.delete(member)
    await db.commit()
    return ResponseBase(data={"id": str(member_id)}, message="წევრი წაიშალა")


# ═══════════════════════ Time tracking — project timesheets ═══════════════════

@router.get("/{project_id}/timesheets", response_model=ResponseBase[dict])
async def list_project_timesheets(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_access")),
):
    rows = (await db.execute(
        select(ProjectTimesheet).where(
            ProjectTimesheet.project_id == project_id,
            ProjectTimesheet.company_id == current_user.company_id,
        ).options(selectinload(ProjectTimesheet.user))
        .order_by(ProjectTimesheet.work_date.desc()).limit(200)
    )).scalars().all()
    total_hours = sum((t.hours for t in rows), Decimal("0"))
    return ResponseBase(data={
        "total_hours": float(total_hours),
        "items": [{
            "id": str(t.id), "project_id": str(t.project_id),
            "task_id": str(t.task_id) if t.task_id else None,
            "user_id": str(t.user_id),
            "user_name": t.user.full_name if t.user else None,
            "work_date": t.work_date.isoformat(),
            "hours": float(t.hours), "billable": t.billable,
            "description": t.description,
        } for t in rows],
    })


@router.post("/{project_id}/timesheets", response_model=ResponseBase[dict], status_code=201)
async def add_timesheet_entry(
    project_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_edit")),
):
    proj = (await db.execute(select(Project).where(
        Project.id == project_id, Project.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="პროექტი არ მოიძებნა")

    # resolve hourly rate: explicit > member rate > project member default 0
    hourly_rate = Decimal(str(data.get("hourly_rate") or 0))
    if hourly_rate == 0:
        member_rate = (await db.execute(select(ProjectMember.hourly_rate).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == (data.get("user_id") or current_user.id),
            ProjectMember.company_id == current_user.company_id,
        ))).scalar_one_or_none()
        hourly_rate = Decimal(str(member_rate)) if member_rate else Decimal("0")

    hours = Decimal(str(data.get("hours", 0)))
    billable = bool(data.get("billable", True))
    billed_amount = (hours * hourly_rate).quantize(Decimal("0.01")) if billable else Decimal("0")

    entry = ProjectTimesheet(
        company_id=current_user.company_id, project_id=project_id,
        task_id=data.get("task_id"),
        user_id=data.get("user_id") or current_user.id,
        work_date=date.fromisoformat(data["work_date"]),
        hours=hours,
        description=data.get("description"),
        billable=billable,
        hourly_rate=hourly_rate,
        billed_amount=billed_amount,
    )
    db.add(entry)
    await db.flush()
    # roll hours-based cost into project spent_amount (member rate = internal cost)
    cost_rate = (await db.execute(select(ProjectMember.hourly_rate).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == entry.user_id,
        ProjectMember.company_id == current_user.company_id,
    ))).scalar() or Decimal("0")
    proj.spent_amount = (proj.spent_amount or Decimal("0")) + hours * Decimal(str(cost_rate or 0))
    # billable revenue rolls into project revenue_amount (Odoo: timesheet billing)
    if billable and billed_amount > 0:
        proj.revenue_amount = (proj.revenue_amount or Decimal("0")) + billed_amount
    await db.commit()
    await db.refresh(entry)
    return ResponseBase(data={
        "id": str(entry.id),
        "hourly_rate": float(hourly_rate),
        "billed_amount": float(billed_amount),
        "billed": entry.billed,
    }, message="დრო დაფიქსირდა")


@router.delete("/timesheets/{entry_id}", response_model=ResponseBase[dict])
async def delete_timesheet_entry(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_edit")),
):
    entry = (await db.execute(select(ProjectTimesheet).where(
        ProjectTimesheet.id == entry_id, ProjectTimesheet.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="ჩანაწერი არ მოიძებნა")
    await db.delete(entry)
    await db.commit()
    return ResponseBase(data={"id": str(entry_id)}, message="ჩანაწერი წაიშალა")


# ═══════════════════════ Resource utilization dashboard ═══════════════════════

@router.get("/resources/utilization", response_model=ResponseBase[list[dict]])
async def resource_utilization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_access")),
):
    """Per-user load: sum of allocations across active projects."""
    members = (await db.execute(
        select(ProjectMember).where(ProjectMember.company_id == current_user.company_id)
        .options(selectinload(ProjectMember.user), selectinload(ProjectMember.project))
    )).scalars().all()
    by_user: dict = {}
    for m in members:
        if m.project and m.project.status != "cancelled":
            key = str(m.user_id)
            agg = by_user.setdefault(key, {
                "user_id": key, "user_name": m.user.full_name if m.user else None,
                "total_allocation": Decimal("0"), "project_count": 0, "projects": [],
            })
            agg["total_allocation"] += m.allocation_percent
            agg["project_count"] += 1
            agg["projects"].append({
                "project_id": str(m.project_id), "project_name": m.project.name,
                "allocation_percent": float(m.allocation_percent), "role": m.role,
            })
    return ResponseBase(data=[{
        **{k: (float(v) if isinstance(v, Decimal) else v) for k, v in u.items() if k != "projects"},
        "projects": u["projects"],
    } for u in by_user.values()])


# ═══════════════════════ Timesheet billing (Odoo) ═════════════════════════════

@router.post("/{project_id}/timesheets/{entry_id}/mark-billed", response_model=ResponseBase[dict])
async def mark_timesheet_billed(
    project_id: UUID,
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_edit")),
):
    """Mark a timesheet entry as billed (invoice issued / sent to client)."""
    entry = (await db.execute(select(ProjectTimesheet).where(
        ProjectTimesheet.id == entry_id,
        ProjectTimesheet.project_id == project_id,
        ProjectTimesheet.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="ჩანაწერი არ მოიძებნა")
    if entry.billed:
        raise HTTPException(status_code=409, detail="ჩანაწერი უკვე დაბილინგებულია")
    entry.billed = True
    entry.billed_at = datetime.utcnow()
    await db.commit()
    return ResponseBase(data={
        "id": str(entry.id), "billed": True, "billed_amount": float(entry.billed_amount),
    }, message="ჩანაწერი დაბილინგდა")


@router.get("/{project_id}/billing-summary", response_model=ResponseBase[dict])
async def project_billing_summary(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("projects", "can_access")),
):
    """Timesheet billing summary: billable hours, unbilled value, billed value."""
    proj = (await db.execute(select(Project).where(
        Project.id == project_id, Project.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="პროექტი არ მოიძებნა")

    rows = (await db.execute(select(ProjectTimesheet).where(
        ProjectTimesheet.project_id == project_id,
        ProjectTimesheet.company_id == current_user.company_id,
    ))).scalars().all()

    total_hours = sum(float(r.hours) for r in rows)
    billable_hours = sum(float(r.hours) for r in rows if r.billable)
    unbilled_value = sum(float(r.billed_amount) for r in rows if r.billable and not r.billed)
    billed_value = sum(float(r.billed_amount) for r in rows if r.billed)
    cost_value = sum(float(r.hours) * float(r.hourly_rate) for r in rows if not r.billable)  # non-billable at rate

    return ResponseBase(data={
        "total_hours": round(total_hours, 2),
        "billable_hours": round(billable_hours, 2),
        "unbilled_value": round(unbilled_value, 2),
        "billed_value": round(billed_value, 2),
        "project_revenue": float(proj.revenue_amount or 0),
        "project_spent": float(proj.spent_amount or 0),
    })

"""Tasks enhanced: kanban, calendar, analytics, bulk actions, export."""
from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.task import Task, TaskStatus
from app.schemas.common import ResponseBase
from app.core.time import utc_now
from pydantic import BaseModel, Field
from io import BytesIO
import openpyxl
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/tasks", tags=["დავალებები — გაძლიერებული"])


# ── Kanban (grouped by status) ─────────────────────────────────────────────────

class KanbanColumn(BaseModel):
    status: str
    status_label: str
    count: int
    tasks: list[dict]


class KanbanBoard(BaseModel):
    columns: list[KanbanColumn]


@router.get("/kanban", response_model=ResponseBase[KanbanBoard])
async def task_kanban(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("tasks", "can_access")),
):
    status_labels = {"todo": "გასაკეთებელი", "in_progress": "მიმდინარე", "done": "დასრულებული", "cancelled": "გაუქმებული"}
    company_id = current_user.company_id

    columns = []
    for status_key in ["todo", "in_progress", "done", "cancelled"]:
        rows = (await db.execute(
            select(Task)
            .where(Task.company_id == company_id, Task.status == status_key)
            .options(selectinload(Task.assignee))
            .order_by(Task.priority.desc(), Task.due_date.asc().nulls_last())
            .limit(20)
        )).scalars().all()

        tasks = []
        for t in rows:
            tasks.append({
                "id": str(t.id),
                "title": t.title,
                "priority": t.priority,
                "due_date": str(t.due_date) if t.due_date else None,
                "assigned_to_name": t.assignee.full_name if t.assignee else None,
            })

        columns.append(KanbanColumn(
            status=status_key, status_label=status_labels.get(status_key, status_key),
            count=len(tasks), tasks=tasks,
        ))

    return ResponseBase(data=KanbanBoard(columns=columns))


# ── Calendar ────────────────────────────────────────────────────────────────────

class CalendarEvent(BaseModel):
    id: UUID
    title: str
    start: str  # ISO date
    end: str | None
    status: str
    priority: str
    assigned_to_name: str | None


@router.get("/calendar", response_model=ResponseBase[list[CalendarEvent]])
async def task_calendar(
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("tasks", "can_access")),
):
    company_id = current_user.company_id
    query = select(Task).where(
        Task.company_id == company_id,
        Task.due_date.isnot(None),
        Task.status.notin_([TaskStatus.CANCELLED.value]),
    ).options(selectinload(Task.assignee))

    if date_from:
        query = query.where(Task.due_date >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(Task.due_date <= datetime.fromisoformat(date_to))

    query = query.order_by(Task.due_date)
    rows = (await db.execute(query)).scalars().all()

    events = []
    for t in rows:
        events.append(CalendarEvent(
            id=t.id, title=t.title,
            start=t.due_date.isoformat() if t.due_date else "",
            end=None, status=t.status, priority=t.priority,
            assigned_to_name=t.assignee.full_name if t.assignee else None,
        ))

    return ResponseBase(data=events)


# ── Analytics ────────────────────────────────────────────────────────────────────

class TaskAnalytics(BaseModel):
    total: int
    todo: int
    in_progress: int
    done: int
    overdue: int
    high_priority: int
    my_tasks: int
    completion_rate: float


@router.get("/analytics", response_model=ResponseBase[TaskAnalytics])
async def task_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("tasks", "can_access")),
):
    company_id = current_user.company_id
    now = utc_now()

    total = (await db.execute(select(func.count(Task.id)).where(Task.company_id == company_id))).scalar()
    todo = (await db.execute(select(func.count(Task.id)).where(Task.company_id == company_id, Task.status == "todo"))).scalar()
    in_progress = (await db.execute(select(func.count(Task.id)).where(Task.company_id == company_id, Task.status == "in_progress"))).scalar()
    done = (await db.execute(select(func.count(Task.id)).where(Task.company_id == company_id, Task.status == "done"))).scalar()
    overdue = (await db.execute(
        select(func.count(Task.id)).where(
            Task.company_id == company_id,
            Task.due_date < now,
            Task.status.notin_(["done", "cancelled"]),
        )
    )).scalar()
    high = (await db.execute(select(func.count(Task.id)).where(Task.company_id == company_id, Task.priority == "high", Task.status.notin_(["done", "cancelled"])))).scalar()
    my = (await db.execute(select(func.count(Task.id)).where(Task.company_id == company_id, Task.assigned_to == current_user.id, Task.status.notin_(["done", "cancelled"])))).scalar()

    total_decided = (todo or 0) + (in_progress or 0) + (done or 0)
    rate = (done or 0) / total_decided * 100 if total_decided > 0 else 0

    return ResponseBase(data=TaskAnalytics(
        total=total or 0, todo=todo or 0, in_progress=in_progress or 0,
        done=done or 0, overdue=overdue or 0, high_priority=high or 0,
        my_tasks=my or 0, completion_rate=round(rate, 1),
    ))


# ── Bulk Actions ────────────────────────────────────────────────────────────────

class BulkTaskUpdate(BaseModel):
    ids: list[UUID]
    status: str = Field(..., max_length=20)


@router.post("/bulk/status", response_model=ResponseBase[dict])
async def bulk_update_task_status(
    data: BulkTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("tasks", "can_edit")),
):
    result = await db.execute(
        update(Task)
        .where(Task.id.in_(data.ids), Task.company_id == current_user.company_id)
        .values(status=data.status)
    )
    await db.flush()
    return ResponseBase(data={"updated": result.rowcount, "status": data.status})


# ── Export ──────────────────────────────────────────────────────────────────────

@router.get("/export")
async def export_tasks(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("tasks", "can_access")),
):
    filters = [Task.company_id == current_user.company_id]
    if status:
        filters.append(Task.status == status)

    rows = (await db.execute(
        select(Task).where(*filters)
        .options(selectinload(Task.assignee), selectinload(Task.client))
        .order_by(Task.created_at.desc())
    )).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "დავალებები"
    ws.append(["სათაური", "სტატუსი", "პრიორიტეტი", "ვადა", "შემსრულებელი", "კლიენტი", "შექმნის თარიღი"])
    for t in rows:
        ws.append([t.title, t.status, t.priority, str(t.due_date or ""),
                   t.assignee.full_name if t.assignee else "",
                   t.client.name if t.client else "", str(t.created_at)])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=tasks.xlsx"})

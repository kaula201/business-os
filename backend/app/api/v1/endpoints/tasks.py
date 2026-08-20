# backend/app/api/v1/endpoints/tasks.py
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional
from uuid import UUID
import os
import shutil
import uuid as uuid_lib

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.time import utc_now
from app.models.user import User
from app.models.task import (
    Task, TaskComment, TaskAttachment, TaskHistory,
    TaskReminder, TaskDependency, TaskStatus
)
from app.models.audit import AuditLog
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse,
    TaskCommentCreate, TaskCommentResponse,
    TaskAttachmentResponse,
    TaskHistoryResponse,
    TaskReminderCreate, TaskReminderUpdate, TaskReminderResponse,
    TaskDependencyCreate, TaskDependencyResponse,
    ActivityFeedItem,
)
from app.schemas.common import ResponseBase, PaginatedResponse

router = APIRouter(prefix="/tasks", tags=["დავალებები"])

# ── Upload directory ───────────────────────────────────────────────────────────
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads", "tasks")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _log_history(
    db: AsyncSession,
    task_id: UUID,
    company_id: UUID,
    user_id: UUID | None,
    action: str,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    description: str | None = None,
):
    """Create a task history entry and an audit log entry."""
    history = TaskHistory(
        task_id=task_id,
        company_id=company_id,
        user_id=user_id,
        action=action,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        description=description,
    )
    db.add(history)

    audit = AuditLog(
        company_id=company_id,
        user_id=user_id,
        action=f"task_{action}",
        entity_type="task",
        entity_id=task_id,
        details=description or f"{action}: {field_name} {old_value} -> {new_value}" if field_name else action,
    )
    db.add(audit)


async def _get_task_or_404(
    db: AsyncSession, task_id: UUID, company_id: UUID
) -> Task:
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.company_id == company_id).options(
            selectinload(Task.assignee),
            selectinload(Task.client),
            selectinload(Task.order),
            selectinload(Task.project),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="დავალება არ მოიძებნა")
    return task


def _enrich_task_response(task: Task) -> TaskResponse:
    resp = TaskResponse.model_validate(task)
    resp.assigned_to_name = task.assignee.full_name if task.assignee else None
    resp.client_name = task.client.name if task.client else None
    resp.order_number = task.order.order_number if task.order else None
    resp.project_name = task.project.name if task.project else None
    resp.created_by = task.created_by
    return resp


# ── List / Get / Create / Update ──────────────────────────────────────────────

@router.get("/", response_model=ResponseBase[PaginatedResponse[TaskListResponse]])
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    assigned_to_me: bool = False,
    overdue: bool = False,
    project_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Task).where(Task.company_id == current_user.company_id).options(
        selectinload(Task.assignee), selectinload(Task.client),
        selectinload(Task.order), selectinload(Task.project),
    )

    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    if search:
        query = query.where(Task.title.ilike(f"%{search}%"))
    if assigned_to_me:
        query = query.where(Task.assigned_to == current_user.id)
    if overdue:
        query = query.where(
            Task.due_date < utc_now(),
            Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED])
        )
    if project_id:
        query = query.where(Task.project_id == project_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    tasks = result.scalars().all()

    items = []
    for t in tasks:
        items.append(TaskListResponse(
            id=t.id,
            title=t.title,
            status=t.status,
            priority=t.priority,
            due_date=t.due_date,
            assigned_to_name=t.assignee.full_name if t.assignee else None,
            client_name=t.client.name if t.client else None,
            order_number=t.order.order_number if t.order else None,
            project_name=t.project.name if t.project else None,
        ))

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    ))


@router.get("/{task_id}", response_model=ResponseBase[TaskResponse])
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_task_or_404(db, task_id, current_user.company_id)
    return ResponseBase(data=_enrich_task_response(task))


@router.post("/", response_model=ResponseBase[TaskResponse])
async def create_task(
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = Task(
        company_id=current_user.company_id,
        client_id=data.client_id,
        order_id=data.order_id,
        project_id=data.project_id,
        parent_id=data.parent_id,
        title=data.title,
        description=data.description,
        assigned_to=data.assigned_to,
        priority=data.priority,
        due_date=data.due_date,
        recurrence=data.recurrence,
        recurrence_end=data.recurrence_end,
        created_by=current_user.id,
    )
    db.add(task)
    await db.flush()

    await _log_history(
        db, task.id, current_user.company_id, current_user.id,
        action="created",
        description=f"შეიქმნა დავალება: {data.title}",
    )

    return ResponseBase(data=_enrich_task_response(task))


@router.patch("/{task_id}", response_model=ResponseBase[TaskResponse])
async def update_task(
    task_id: UUID,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_task_or_404(db, task_id, current_user.company_id)

    # Dependency gate (Odoo-style): cannot start a task whose blockers are not done
    if data.status == "in_progress" and task.status != "in_progress":
        blockers = (await db.execute(
            select(TaskDependency).where(
                TaskDependency.task_id == task.id,
                TaskDependency.dependency_type == "blocked_by",
            )
        )).scalars().all()
        if blockers:
            blocker_ids = [b.depends_on_task_id for b in blockers]
            blocker_tasks = (await db.execute(
                select(Task).where(Task.id.in_(blocker_ids))
            )).scalars().all()
            unfinished = [t for t in blocker_tasks if t.status != "done"]
            if unfinished:
                names = ", ".join(t.title for t in unfinished[:3])
                raise HTTPException(
                    status_code=409,
                    detail=f"დავალება ვერ დაიწყება — დაბლოკილია: {names}",
                )

    update_data = data.model_dump(exclude_unset=True)
    tracked_fields = {"title", "description", "status", "priority", "due_date", "assigned_to", "client_id", "order_id", "project_id", "parent_id", "recurrence", "recurrence_end"}

    for field, value in update_data.items():
        old_value = getattr(task, field, None)
        if field in tracked_fields and old_value != value:
            field_labels = {
                "title": "სათაური", "description": "აღწერა", "status": "სტატუსი",
                "priority": "პრიორიტეტი", "due_date": "ვადა", "assigned_to": "შემსრულებელი",
                "client_id": "კლიენტი", "order_id": "შეკვეთა", "project_id": "პროექტი",
            }
            action = "updated"
            if field == "status":
                action = "status_changed"
            elif field == "assigned_to":
                action = "assigned"

            await _log_history(
                db, task.id, current_user.company_id, current_user.id,
                action=action,
                field_name=field_labels.get(field, field),
                old_value=str(old_value) if old_value else None,
                new_value=str(value) if value else None,
            )
        setattr(task, field, value)

    # Recurrence (Odoo-style): when a recurring task is done, auto-create the next one
    if task.status == "done" and task.recurrence:
        from datetime import timedelta
        base = task.due_date or utc_now()
        if task.recurrence == "daily":
            next_due = base + timedelta(days=1)
        elif task.recurrence == "weekly":
            next_due = base + timedelta(weeks=1)
        elif task.recurrence == "monthly":
            month = base.month + 1
            year = base.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            next_due = base.replace(year=year, month=month)
        else:
            next_due = None
        if next_due and (not task.recurrence_end or next_due.date() <= task.recurrence_end):
            db.add(Task(
                company_id=current_user.company_id,
                client_id=task.client_id, order_id=task.order_id, project_id=task.project_id,
                parent_id=task.parent_id,
                title=task.title, description=task.description,
                status="todo", priority=task.priority,
                due_date=next_due, assigned_to=task.assigned_to,
                recurrence=task.recurrence, recurrence_end=task.recurrence_end,
                created_by=current_user.id,
            ))

    await db.flush()
    await db.refresh(task)
    return ResponseBase(data=_enrich_task_response(task))


# ── Comments ───────────────────────────────────────────────────────────────────

@router.get("/{task_id}/comments", response_model=ResponseBase[list[TaskCommentResponse]])
async def list_comments(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_task_or_404(db, task_id, current_user.company_id)

    result = await db.execute(
        select(TaskComment)
        .where(TaskComment.task_id == task_id)
        .options(selectinload(TaskComment.user))
        .order_by(TaskComment.created_at)
    )
    comments = result.scalars().all()

    items = []
    for c in comments:
        resp = TaskCommentResponse.model_validate(c)
        resp.user_name = c.user.full_name if c.user else None
        items.append(resp)

    return ResponseBase(data=items)


@router.post("/{task_id}/comments", response_model=ResponseBase[TaskCommentResponse])
async def add_comment(
    task_id: UUID,
    data: TaskCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_task_or_404(db, task_id, current_user.company_id)

    comment = TaskComment(
        task_id=task_id,
        user_id=current_user.id,
        content=data.content,
    )
    db.add(comment)
    await db.flush()

    await _log_history(
        db, task.id, current_user.company_id, current_user.id,
        action="comment_added",
        description=f"დაემატა კომენტარი: {data.content[:100]}{'...' if len(data.content) > 100 else ''}",
    )

    resp = TaskCommentResponse.model_validate(comment)
    resp.user_name = current_user.full_name
    return ResponseBase(data=resp)


# ── Attachments ────────────────────────────────────────────────────────────────

@router.get("/{task_id}/attachments", response_model=ResponseBase[list[TaskAttachmentResponse]])
async def list_attachments(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_task_or_404(db, task_id, current_user.company_id)

    result = await db.execute(
        select(TaskAttachment)
        .where(TaskAttachment.task_id == task_id)
        .options(selectinload(TaskAttachment.uploader))
        .order_by(TaskAttachment.created_at.desc())
    )
    attachments = result.scalars().all()

    items = []
    for a in attachments:
        resp = TaskAttachmentResponse.model_validate(a)
        resp.uploader_name = a.uploader.full_name if a.uploader else None
        items.append(resp)

    return ResponseBase(data=items)


@router.post("/{task_id}/attachments", response_model=ResponseBase[TaskAttachmentResponse])
async def upload_attachment(
    task_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_task_or_404(db, task_id, current_user.company_id)

    # Save file to disk
    file_id = uuid_lib.uuid4()
    ext = os.path.splitext(file.filename or "file")[1]
    safe_filename = f"{file_id}{ext}"
    task_upload_dir = os.path.join(UPLOAD_DIR, str(task_id))
    os.makedirs(task_upload_dir, exist_ok=True)
    file_path = os.path.join(task_upload_dir, safe_filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    attachment = TaskAttachment(
        task_id=task_id,
        company_id=current_user.company_id,
        uploaded_by=current_user.id,
        filename=file.filename or "file",
        file_size=len(content),
        mime_type=file.content_type or "application/octet-stream",
        file_path=file_path,
    )
    db.add(attachment)
    await db.flush()

    await _log_history(
        db, task.id, current_user.company_id, current_user.id,
        action="attachment_added",
        description=f"დაერთო ფაილი: {file.filename} ({len(content)} bytes)",
    )

    resp = TaskAttachmentResponse.model_validate(attachment)
    resp.uploader_name = current_user.full_name
    return ResponseBase(data=resp)


@router.delete("/{task_id}/attachments/{attachment_id}", response_model=ResponseBase[dict])
async def delete_attachment(
    task_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_task_or_404(db, task_id, current_user.company_id)

    result = await db.execute(
        select(TaskAttachment).where(
            TaskAttachment.id == attachment_id,
            TaskAttachment.task_id == task_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="ფაილი არ მოიძებნა")

    # Delete file from disk
    if os.path.exists(attachment.file_path):
        os.remove(attachment.file_path)

    await db.delete(attachment)
    await db.flush()

    return ResponseBase(data={"deleted": True})


# ── History / Activity Feed ────────────────────────────────────────────────────

@router.get("/{task_id}/history", response_model=ResponseBase[list[TaskHistoryResponse]])
async def list_history(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_task_or_404(db, task_id, current_user.company_id)

    result = await db.execute(
        select(TaskHistory)
        .where(TaskHistory.task_id == task_id)
        .options(selectinload(TaskHistory.user))
        .order_by(TaskHistory.created_at.desc())
        .limit(100)
    )
    history = result.scalars().all()

    items = []
    for h in history:
        resp = TaskHistoryResponse.model_validate(h)
        resp.user_name = h.user.full_name if h.user else None
        items.append(resp)

    return ResponseBase(data=items)


@router.get("/{task_id}/activity", response_model=ResponseBase[list[ActivityFeedItem]])
async def get_activity_feed(
    task_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Combined activity feed: history + comments + attachments."""
    await _get_task_or_404(db, task_id, current_user.company_id)

    # Fetch history entries
    history_result = await db.execute(
        select(TaskHistory)
        .where(TaskHistory.task_id == task_id)
        .options(selectinload(TaskHistory.user))
        .order_by(TaskHistory.created_at.desc())
        .limit(limit)
    )
    history_entries = history_result.scalars().all()

    # Fetch comments
    comments_result = await db.execute(
        select(TaskComment)
        .where(TaskComment.task_id == task_id)
        .options(selectinload(TaskComment.user))
        .order_by(TaskComment.created_at.desc())
        .limit(limit)
    )
    comment_entries = comments_result.scalars().all()

    # Fetch attachments
    attachments_result = await db.execute(
        select(TaskAttachment)
        .where(TaskAttachment.task_id == task_id)
        .options(selectinload(TaskAttachment.uploader))
        .order_by(TaskAttachment.created_at.desc())
        .limit(limit)
    )
    attachment_entries = attachments_result.scalars().all()

    feed: list[ActivityFeedItem] = []

    for h in history_entries:
        feed.append(ActivityFeedItem(
            id=h.id,
            type="history",
            user_name=h.user.full_name if h.user else None,
            action=h.action,
            description=h.description,
            created_at=h.created_at,
        ))

    for c in comment_entries:
        feed.append(ActivityFeedItem(
            id=c.id,
            type="comment",
            user_name=c.user.full_name if c.user else None,
            content=c.content,
            created_at=c.created_at,
        ))

    for a in attachment_entries:
        feed.append(ActivityFeedItem(
            id=a.id,
            type="attachment",
            user_name=a.uploader.full_name if a.uploader else None,
            filename=a.filename,
            created_at=a.created_at,
        ))

    # Sort by created_at descending, take top N
    feed.sort(key=lambda x: x.created_at, reverse=True)
    feed = feed[:limit]

    return ResponseBase(data=feed)


# ── Reminders ──────────────────────────────────────────────────────────────────

@router.get("/{task_id}/reminders", response_model=ResponseBase[list[TaskReminderResponse]])
async def list_reminders(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_task_or_404(db, task_id, current_user.company_id)

    result = await db.execute(
        select(TaskReminder)
        .where(TaskReminder.task_id == task_id)
        .options(selectinload(TaskReminder.user))
        .order_by(TaskReminder.remind_at)
    )
    reminders = result.scalars().all()

    items = [TaskReminderResponse.model_validate(r) for r in reminders]
    return ResponseBase(data=items)


@router.post("/{task_id}/reminders", response_model=ResponseBase[TaskReminderResponse])
async def create_reminder(
    task_id: UUID,
    data: TaskReminderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_task_or_404(db, task_id, current_user.company_id)

    reminder = TaskReminder(
        task_id=task_id,
        company_id=current_user.company_id,
        user_id=current_user.id,
        remind_at=data.remind_at,
        notification_type=data.notification_type,
    )
    db.add(reminder)
    await db.flush()

    await _log_history(
        db, task.id, current_user.company_id, current_user.id,
        action="reminder_set",
        description=f"დაემატა შეხსენება: {data.remind_at.isoformat()} ({data.notification_type})",
    )

    return ResponseBase(data=TaskReminderResponse.model_validate(reminder))


@router.patch("/{task_id}/reminders/{reminder_id}", response_model=ResponseBase[TaskReminderResponse])
async def update_reminder(
    task_id: UUID,
    reminder_id: UUID,
    data: TaskReminderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_task_or_404(db, task_id, current_user.company_id)

    result = await db.execute(
        select(TaskReminder).where(
            TaskReminder.id == reminder_id,
            TaskReminder.task_id == task_id,
        )
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="შეხსენება არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(reminder, field, value)

    await db.flush()
    return ResponseBase(data=TaskReminderResponse.model_validate(reminder))


@router.delete("/{task_id}/reminders/{reminder_id}", response_model=ResponseBase[dict])
async def delete_reminder(
    task_id: UUID,
    reminder_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_task_or_404(db, task_id, current_user.company_id)

    result = await db.execute(
        select(TaskReminder).where(
            TaskReminder.id == reminder_id,
            TaskReminder.task_id == task_id,
        )
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="შეხსენება არ მოიძებნა")

    await db.delete(reminder)
    await db.flush()

    return ResponseBase(data={"deleted": True})


# ── Dependencies ───────────────────────────────────────────────────────────────

@router.get("/{task_id}/dependencies", response_model=ResponseBase[list[TaskDependencyResponse]])
async def list_dependencies(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_task_or_404(db, task_id, current_user.company_id)

    result = await db.execute(
        select(TaskDependency)
        .where(TaskDependency.task_id == task_id)
        .options(selectinload(TaskDependency.depends_on_task))
        .order_by(TaskDependency.created_at.desc())
    )
    deps = result.scalars().all()

    items = []
    for d in deps:
        resp = TaskDependencyResponse.model_validate(d)
        resp.depends_on_task_title = d.depends_on_task.title if d.depends_on_task else None
        resp.depends_on_task_status = d.depends_on_task.status if d.depends_on_task else None
        items.append(resp)

    return ResponseBase(data=items)


@router.get("/{task_id}/dependents", response_model=ResponseBase[list[TaskDependencyResponse]])
async def list_dependents(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tasks that depend on this task (reverse dependencies)."""
    await _get_task_or_404(db, task_id, current_user.company_id)

    result = await db.execute(
        select(TaskDependency)
        .where(TaskDependency.depends_on_task_id == task_id)
        .options(selectinload(TaskDependency.task))
        .order_by(TaskDependency.created_at.desc())
    )
    deps = result.scalars().all()

    items = []
    for d in deps:
        resp = TaskDependencyResponse.model_validate(d)
        resp.depends_on_task_id = d.task_id
        resp.depends_on_task_title = d.task.title if d.task else None
        resp.depends_on_task_status = d.task.status if d.task else None
        items.append(resp)

    return ResponseBase(data=items)


@router.post("/{task_id}/dependencies", response_model=ResponseBase[TaskDependencyResponse])
async def create_dependency(
    task_id: UUID,
    data: TaskDependencyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_task_or_404(db, task_id, current_user.company_id)

    # Verify the target task exists and belongs to same company
    target_result = await db.execute(
        select(Task).where(
            Task.id == data.depends_on_task_id,
            Task.company_id == current_user.company_id,
        )
    )
    target_task = target_result.scalar_one_or_none()
    if not target_task:
        raise HTTPException(status_code=404, detail="დამოკიდებული დავალება არ მოიძებნა")

    # Prevent self-dependency
    if data.depends_on_task_id == task_id:
        raise HTTPException(status_code=400, detail="დავალება არ შეიძლება საკუთარ თავზე იყოს დამოკიდებული")

    # Check for duplicate
    existing = await db.execute(
        select(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_task_id == data.depends_on_task_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="ეს დამოკიდებულება უკვე არსებობს")

    dep = TaskDependency(
        task_id=task_id,
        depends_on_task_id=data.depends_on_task_id,
        company_id=current_user.company_id,
        dependency_type=data.dependency_type.value if hasattr(data.dependency_type, 'value') else data.dependency_type,
        created_by=current_user.id,
    )
    db.add(dep)
    await db.flush()

    await _log_history(
        db, task.id, current_user.company_id, current_user.id,
        action="dependency_added",
        description=f"დაემატა დამოკიდებულება: {task.title} -> {target_task.title} ({data.dependency_type})",
    )

    resp = TaskDependencyResponse.model_validate(dep)
    resp.depends_on_task_title = target_task.title
    resp.depends_on_task_status = target_task.status
    return ResponseBase(data=resp)


@router.delete("/{task_id}/dependencies/{dependency_id}", response_model=ResponseBase[dict])
async def delete_dependency(
    task_id: UUID,
    dependency_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_task_or_404(db, task_id, current_user.company_id)

    result = await db.execute(
        select(TaskDependency).where(
            TaskDependency.id == dependency_id,
            TaskDependency.task_id == task_id,
        )
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=404, detail="დამოკიდებულება არ მოიძებნა")

    await db.delete(dep)
    await db.flush()

    return ResponseBase(data={"deleted": True})

# backend/app/schemas/task.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID
from app.models.task import TaskStatus, TaskPriority, TaskDependencyType


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    assigned_to: Optional[UUID] = None
    due_date: Optional[datetime] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    client_id: Optional[UUID] = None
    order_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    recurrence: Optional[str] = None
    recurrence_end: Optional[date] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[datetime] = None
    assigned_to: Optional[UUID] = None
    client_id: Optional[UUID] = None
    order_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    recurrence: Optional[str] = None
    recurrence_end: Optional[date] = None


class TaskResponse(BaseModel):
    id: UUID
    company_id: UUID
    client_id: Optional[UUID]
    client_name: Optional[str] = None
    order_id: Optional[UUID]
    order_number: Optional[str] = None
    project_id: Optional[UUID] = None
    project_name: Optional[str] = None
    title: str
    description: Optional[str]
    status: str
    priority: str
    due_date: Optional[datetime]
    assigned_to: Optional[UUID]
    assigned_to_name: Optional[str] = None
    created_by: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    recurrence: Optional[str] = None
    recurrence_end: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    id: UUID
    title: str
    status: str
    priority: str
    due_date: Optional[datetime]
    assigned_to_name: Optional[str] = None
    client_name: Optional[str] = None
    order_number: Optional[str] = None
    project_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── Comments ────────────────────────────────────────────────────────────────────

class TaskCommentCreate(BaseModel):
    content: str = Field(..., min_length=1)


class TaskCommentResponse(BaseModel):
    id: UUID
    task_id: UUID
    user_id: Optional[UUID]
    user_name: Optional[str] = None
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Attachments ─────────────────────────────────────────────────────────────────

class TaskAttachmentResponse(BaseModel):
    id: UUID
    task_id: UUID
    filename: str
    file_size: int
    mime_type: str
    uploaded_by: Optional[UUID]
    uploader_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── History / Activity Feed ─────────────────────────────────────────────────────

class TaskHistoryResponse(BaseModel):
    id: UUID
    task_id: UUID
    user_id: Optional[UUID]
    user_name: Optional[str] = None
    action: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Reminders ───────────────────────────────────────────────────────────────────

class TaskReminderCreate(BaseModel):
    remind_at: datetime
    notification_type: str = "email"


class TaskReminderUpdate(BaseModel):
    remind_at: Optional[datetime] = None
    notification_type: Optional[str] = None


class TaskReminderResponse(BaseModel):
    id: UUID
    task_id: UUID
    user_id: Optional[UUID]
    remind_at: datetime
    reminded: bool
    reminded_at: Optional[datetime] = None
    notification_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Dependencies ────────────────────────────────────────────────────────────────

class TaskDependencyCreate(BaseModel):
    depends_on_task_id: UUID
    dependency_type: TaskDependencyType = TaskDependencyType.BLOCKED_BY


class TaskDependencyResponse(BaseModel):
    id: UUID
    task_id: UUID
    depends_on_task_id: UUID
    dependency_type: str
    depends_on_task_title: Optional[str] = None
    depends_on_task_status: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Activity Feed (combined) ────────────────────────────────────────────────────

class ActivityFeedItem(BaseModel):
    id: UUID
    type: str  # comment, history, attachment
    user_name: Optional[str] = None
    content: Optional[str] = None
    action: Optional[str] = None
    description: Optional[str] = None
    filename: Optional[str] = None
    created_at: datetime

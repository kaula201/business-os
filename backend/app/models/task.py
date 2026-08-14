import uuid
from datetime import date, datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, func, Boolean, Integer, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskDependencyType(str, enum.Enum):
    BLOCKS = "blocks"
    BLOCKED_BY = "blocked_by"
    RELATES_TO = "relates_to"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    recurrence: Mapped[str | None] = mapped_column(String(20), nullable=True)  # daily|weekly|monthly
    recurrence_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    parent = relationship("Task", remote_side=[id], back_populates="subtasks")
    subtasks = relationship("Task", back_populates="parent", cascade="all, delete-orphan")

    company = relationship("Company", back_populates="tasks")
    client = relationship("Client", back_populates="tasks")
    order = relationship("Order", back_populates="tasks")
    project = relationship("Project")
    assignee = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_tasks")
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_tasks")
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan",
                            order_by="TaskComment.created_at")
    attachments = relationship("TaskAttachment", back_populates="task", cascade="all, delete-orphan",
                               order_by="TaskAttachment.created_at.desc()")
    history = relationship("TaskHistory", back_populates="task", cascade="all, delete-orphan",
                           order_by="TaskHistory.created_at.desc()")
    reminders = relationship("TaskReminder", back_populates="task", cascade="all, delete-orphan")
    dependencies_from = relationship(
        "TaskDependency", foreign_keys="TaskDependency.task_id",
        back_populates="task", cascade="all, delete-orphan"
    )
    dependencies_to = relationship(
        "TaskDependency", foreign_keys="TaskDependency.depends_on_task_id",
        back_populates="depends_on_task", cascade="all, delete-orphan"
    )


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task = relationship("Task", back_populates="comments")
    user = relationship("User", foreign_keys=[user_id])


class TaskAttachment(Base):
    """File attachments for tasks."""
    __tablename__ = "task_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream", nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task = relationship("Task", back_populates="attachments")
    uploader = relationship("User", foreign_keys=[uploaded_by])


class TaskHistory(Base):
    """Audit log / activity feed for tasks."""
    __tablename__ = "task_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # action: created, updated, status_changed, assigned, comment_added, attachment_added, reminder_set, etc.
    field_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task = relationship("Task", back_populates="history")
    user = relationship("User", foreign_keys=[user_id])


class TaskReminder(Base):
    """Due date reminders for tasks."""
    __tablename__ = "task_reminders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    remind_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reminded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notification_type: Mapped[str] = mapped_column(String(20), default="email", nullable=False)
    # email, in_app, both
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task = relationship("Task", back_populates="reminders")
    user = relationship("User", foreign_keys=[user_id])


class TaskDependency(Base):
    """Task dependencies — a task can depend on or block another task."""
    __tablename__ = "task_dependencies"
    __table_args__ = (
        # Prevent duplicate dependency pairs
        None,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    dependency_type: Mapped[str] = mapped_column(String(20), default="blocked_by", nullable=False)
    # blocked_by, blocks, relates_to
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task = relationship("Task", foreign_keys=[task_id], back_populates="dependencies_from")
    depends_on_task = relationship("Task", foreign_keys=[depends_on_task_id], back_populates="dependencies_to")
    creator = relationship("User", foreign_keys=[created_by])

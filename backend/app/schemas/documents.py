"""Pydantic schemas for Document Management module."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Document Category ──────────────────────────────────────────────────────────

class DocumentCategoryBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    parent_id: Optional[UUID] = None
    is_active: bool = True
    sort_order: int = 0
    allowed_extensions: Optional[str] = None
    max_file_size: Optional[int] = None
    retention_days: Optional[int] = None
    retention_policy: str = "indefinite"
    access_roles: Optional[str] = None


class DocumentCategoryCreate(DocumentCategoryBase):
    pass


class DocumentCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    parent_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    allowed_extensions: Optional[str] = None
    max_file_size: Optional[int] = None
    retention_days: Optional[int] = None
    retention_policy: Optional[str] = None
    access_roles: Optional[str] = None


class DocumentCategoryResponse(DocumentCategoryBase):
    id: UUID
    company_id: UUID
    path: Optional[str] = None
    level: int = 0
    created_at: datetime
    updated_at: datetime
    children_count: int = 0
    document_count: int = 0

    model_config = {"from_attributes": True}


class DocumentCategoryTreeResponse(DocumentCategoryResponse):
    """Category with nested children for tree rendering."""
    children: list["DocumentCategoryTreeResponse"] = []

    model_config = {"from_attributes": True}


# ── Document ────────────────────────────────────────────────────────────────────

class DocumentBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    document_type: str = "other"
    tags: Optional[str] = None
    is_template: bool = False


class DocumentCreate(DocumentBase):
    filename: str = Field(..., max_length=500)
    file_size: int = 0
    mime_type: str = "application/octet-stream"
    file_path: str = Field(..., max_length=1000)
    checksum: Optional[str] = None
    retention_days: Optional[int] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    document_type: Optional[str] = None
    tags: Optional[str] = None
    is_archived: Optional[bool] = None
    retention_days: Optional[int] = None


class DocumentResponse(DocumentBase):
    id: UUID
    company_id: UUID
    filename: str
    file_size: int
    mime_type: str
    file_path: str
    has_preview: bool = False
    preview_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    is_archived: bool
    version: int
    approval_status: str = "draft"
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None
    submitted_for_approval_at: Optional[datetime] = None
    retention_days: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    category_name: Optional[str] = None
    uploaded_by_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Document Version ────────────────────────────────────────────────────────────

class DocumentVersionCreate(BaseModel):
    filename: str = Field(..., max_length=500)
    file_size: int = 0
    mime_type: str = "application/octet-stream"
    file_path: str = Field(..., max_length=1000)
    checksum: Optional[str] = None
    change_summary: Optional[str] = None
    notes: Optional[str] = None


class DocumentVersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    filename: str
    file_size: int
    mime_type: str
    file_path: str
    checksum: Optional[str] = None
    change_summary: Optional[str] = None
    is_current: bool = False
    notes: Optional[str] = None
    created_at: datetime
    uploaded_by_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Approval Workflow ───────────────────────────────────────────────────────────

class DocumentSubmitForApproval(BaseModel):
    notes: Optional[str] = None


class DocumentApprovalAction(BaseModel):
    action: str = Field(..., pattern="^(approved|rejected)$")
    notes: Optional[str] = None


class DocumentPublishAction(BaseModel):
    notes: Optional[str] = None


class DocumentApprovalResponse(BaseModel):
    id: UUID
    document_id: UUID
    action: str
    notes: Optional[str] = None
    submitted_by_name: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── File Upload Security ────────────────────────────────────────────────────────

class FileUploadPolicy(BaseModel):
    allowed_extensions: list[str] = Field(default_factory=lambda: [
        "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
        "jpg", "jpeg", "png", "gif", "svg", "webp",
        "txt", "csv", "json", "xml",
        "zip", "rar", "7z",
    ])
    max_file_size: int = 50 * 1024 * 1024  # 50 MB default
    blocked_extensions: list[str] = Field(default_factory=lambda: [
        "exe", "bat", "cmd", "com", "msi", "scr", "vbs",
        "js", "vba", "ps1", "sh", "bin", "dll", "sys",
    ])


# ── Audit Trail ─────────────────────────────────────────────────────────────────

class DocumentAuditLogResponse(BaseModel):
    id: UUID
    action: str
    entity_type: str
    entity_id: Optional[UUID] = None
    details: Optional[str] = None
    user_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

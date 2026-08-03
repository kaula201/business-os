"""Document Management models: DocumentCategory, Document, DocumentVersion, DocumentApproval, DocumentAuditLog."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, Numeric, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DocumentCategory(Base):
    """Document categories / folders with hierarchy, retention, and security rules."""
    __tablename__ = "document_categories"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_doc_category_company_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_categories.id"), nullable=True)
    path: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # materialized path: /root/parent/child
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # depth in hierarchy
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # File upload security rules
    allowed_extensions: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated: pdf,docx,xlsx
    max_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # bytes, null = company default

    # Retention policy
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = indefinite
    retention_policy: Mapped[str] = mapped_column(String(20), default="indefinite", nullable=False)
    # indefinite, timed, destroy_after

    # Access control — which roles can access this category
    access_roles: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated: admin,manager,accountant

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    parent = relationship("DocumentCategory", remote_side="DocumentCategory.id", back_populates="children")
    children = relationship("DocumentCategory", back_populates="parent", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="category")


class Document(Base):
    """Document vault — uploaded files with metadata, approval workflow, and retention."""
    __tablename__ = "documents"

    class ApprovalStatus:
        DRAFT = "draft"
        PENDING = "pending_approval"
        APPROVED = "approved"
        REJECTED = "rejected"
        PUBLISHED = "published"
        CHOICES = [DRAFT, PENDING, APPROVED, REJECTED, PUBLISHED]

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_categories.id"), nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str] = mapped_column(String(50), default="other", nullable=False)
    # contract, invoice_received, report, template, hr_document, other

    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(default=0, nullable=False)  # bytes
    mime_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream", nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)  # server path

    # File preview support
    has_preview: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preview_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # generated preview (PDF thumbnail, etc.)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)

    # Approval workflow
    approval_status: Mapped[str] = mapped_column(String(20), default=ApprovalStatus.DRAFT, nullable=False, index=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_for_approval_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Retention
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # overrides category
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # computed: created_at + retention_days

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    category = relationship("DocumentCategory", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan",
                            order_by="DocumentVersion.version_number.desc()")
    approvals = relationship("DocumentApproval", back_populates="document", cascade="all, delete-orphan",
                             order_by="DocumentApproval.created_at.desc()")


class DocumentVersion(Base):
    """Version history for documents with enhanced metadata."""
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(default=0, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream", nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256 of file content
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # human-readable summary of changes
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # marks the active version
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="versions")


class DocumentApproval(Base):
    """Approval workflow trail for document publishing."""
    __tablename__ = "document_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # submitted, approved, rejected, published
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="approvals")

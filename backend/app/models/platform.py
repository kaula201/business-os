"""Configurable platform: custom fields, workflows, report templates, import mappings."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CustomField(Base):
    """User-defined field attached to any entity (client, order, invoice...)."""

    __tablename__ = "custom_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # client|order|invoice|product|...
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # technical key, e.g. custom_note
    label_ka: Mapped[str] = mapped_column(String(255), nullable=False)
    label_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    field_type: Mapped[str] = mapped_column(String(30), default="text", nullable=False)  # text|number|date|boolean|select|json
    options: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # for select
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class CustomFieldValue(Base):
    """Stored value of a custom field on a specific record."""

    __tablename__ = "custom_field_values"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("custom_fields.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class WorkflowTemplate(Base):
    """Configurable workflow: ordered steps with roles and approvals."""

    __tablename__ = "workflow_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # [{order, name, status_from, status_to, required_role, auto}]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ReportTemplate(Base):
    """Report builder: saved query+layout for Excel/CSV/PDF export."""

    __tablename__ = "report_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    columns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # [{key, label, type}]
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sort_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ImportMapping(Base):
    """Column-mapping blueprint for CSV imports: source column → target field."""

    __tablename__ = "import_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # {source_column: target_field}
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class IndustryTemplate(Base):
    """Pre-built setup blueprint (chart of accounts + modules + fields) by industry."""

    __tablename__ = "industry_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name_ka: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    modules: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    custom_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

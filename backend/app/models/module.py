"""App Module architecture — Odoo-inspired module registry, company modules, and permissions.

AppModule:  catalog of available application modules (CRM, Fleet, GL, Cash, …)
CompanyModule:  which modules a specific company has enabled
ModulePermission:  role-based permission per module (access, create, edit, delete, approve)
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AppModule(Base):
    """Catalog of every available application module."""
    __tablename__ = "app_modules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)  # lucide-react icon name
    route: Mapped[str | None] = mapped_column(String(255), nullable=True)  # frontend route prefix
    category: Mapped[str] = mapped_column(String(50), default="other", nullable=False, index=True)
    # sales, crm, operations, finance, accounting, fleet, hr, settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    depends_on: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # comma-separated list of module codes this module depends on
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    company_modules = relationship("CompanyModule", back_populates="module", cascade="all, delete-orphan")
    permissions = relationship("ModulePermission", back_populates="module", cascade="all, delete-orphan")


class CompanyModule(Base):
    """Tracks which modules a company has enabled/disabled."""
    __tablename__ = "company_modules"
    __table_args__ = (
        UniqueConstraint("company_id", "module_id", name="uq_company_module"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    module_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_modules.id"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    company = relationship("Company", backref="company_modules")
    module = relationship("AppModule", back_populates="company_modules")


class ModulePermission(Base):
    """Granular role-based permissions per module.

    If no row exists for a (module, role) pair, the default is:
      - admin: full access
      - manager: access + create + edit
      - accountant: access (read-only financial)
      - employee: access (read-only operational)
    """
    __tablename__ = "module_permissions"
    __table_args__ = (
        UniqueConstraint("module_id", "role", name="uq_module_permission_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_modules.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    can_access: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_create: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_approve: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    module = relationship("AppModule", back_populates="permissions")

"""Dashboard layout persistence (REQ-DASH: GET/PUT /dashboard/layout).

Server-side per-user widget layout so a role change revokes streams and the
server remains authoritative; localStorage is only a fast-path cache.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DashboardLayout(Base):
    __tablename__ = "dashboard_layouts"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_dashboard_layout_user_company"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    # {view_key: [kpi_key, ...]} — which KPIs each role view shows
    widgets: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<DashboardLayout user={self.user_id} company={self.company_id} widgets={list((self.widgets or {}).keys())}>"

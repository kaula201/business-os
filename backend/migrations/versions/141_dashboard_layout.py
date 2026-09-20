"""141_dashboard_layout

Revision ID: 141_dashboard_layout
Revises: 140_api_webhook_hardening
Create Date: 2026-09-19

Server-side dashboard layout persistence (REQ-DASH: GET/PUT /dashboard/layout).
Per-user, per-company widget (KPI) config stored in JSONB.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "141_dashboard_layout"
down_revision = "140_api_webhook_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_layouts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("widgets", JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "company_id", name="uq_dashboard_layout_user_company"),
    )
    op.create_index("ix_dashboard_layouts_user_company", "dashboard_layouts", ["user_id", "company_id"])


def downgrade() -> None:
    op.drop_table("dashboard_layouts")

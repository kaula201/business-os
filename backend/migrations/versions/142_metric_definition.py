"""142_metric_definition

Revision ID: 142_metric_definition
Revises: 141_dashboard_layout
Create Date: 2026-09-20

Authoritative metric registry (REQ-RPT-01): each KPI defined once with
formula version, source, allowed roles and refresh interval. Serves both
dashboard cards and reports from one source of truth.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "142_metric_definition"
down_revision = "141_dashboard_layout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metric_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("formula", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("formula_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("allowed_roles", JSONB(), nullable=True),
        sa.Column("refresh_interval", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("grain", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "code", "formula_version", name="uq_metric_definition_company_code_version"),
    )
    op.create_index("ix_metric_definitions_company_code", "metric_definitions", ["company_id", "code"])


def downgrade() -> None:
    op.drop_table("metric_definitions")

"""Reports module: export scope preferences.

Adds the report_preferences table storing per-company defaults for the
Reports UI (default date range, export scope, chart grouping).

Revision ID: 046_reports
Revises: 045_warehouse_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "046_reports"
down_revision: Union[str, None] = "045_warehouse_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("default_date_range", sa.String(10), server_default="30d", nullable=False),
        sa.Column("default_export_scope", sa.String(10), server_default="current", nullable=False),
        sa.Column("group_by_month", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_preferences_company",
        "report_preferences",
        ["company_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_report_preferences_company", table_name="report_preferences")
    op.drop_table("report_preferences")

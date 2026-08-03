"""Add accounting period close/reopen controls.
Revision ID: 019_accounting_periods
Revises: 018_nbg_scheduler
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019_accounting_periods"
down_revision: Union[str, None] = "018_nbg_scheduler"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accounting_periods",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="open", nullable=False),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("closed_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("reopened_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reopened_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "year", "month", name="uq_accounting_period_company_month"),
    )
    op.create_index("ix_ap_company_status", "accounting_periods", ["company_id", "status"])
    op.create_table(
        "accounting_period_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("period_id", sa.UUID(as_uuid=True), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ape_period_created", "accounting_period_events", ["period_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ape_period_created", table_name="accounting_period_events")
    op.drop_table("accounting_period_events")
    op.drop_index("ix_ap_company_status", table_name="accounting_periods")
    op.drop_table("accounting_periods")

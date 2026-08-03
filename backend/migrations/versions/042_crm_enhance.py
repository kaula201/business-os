"""Enhance CRM module: next_action_date, last_activity_at for leads.

Revision ID: 042_crm_enhance
Revises: 041_tasks_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "042_crm_enhance"
down_revision: Union[str, None] = "041_tasks_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "crm_leads",
        sa.Column("next_action_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "crm_leads",
        sa.Column("last_activity_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_crm_leads_next_action",
        "crm_leads",
        ["company_id", "next_action_date"],
    )
    op.create_index(
        "ix_crm_leads_last_activity",
        "crm_leads",
        ["company_id", "last_activity_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_crm_leads_last_activity", table_name="crm_leads")
    op.drop_index("ix_crm_leads_next_action", table_name="crm_leads")
    op.drop_column("crm_leads", "last_activity_at")
    op.drop_column("crm_leads", "next_action_date")

"""128_helpdesk_ticket_team_stage

Revision ID: 128_helpdesk_ticket_team_stage
Revises: 127_helpdesk_teams_pipelines
Create Date: 2026-08-20

Team + pipeline stage on helpdesk tickets.
"""
import sqlalchemy as sa
from alembic import op

revision = "128_helpdesk_ticket_team_stage"
down_revision = "127_helpdesk_teams_pipelines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("helpdesk_tickets", sa.Column("team_id", sa.UUID(), sa.ForeignKey("helpdesk_teams.id"), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("pipeline_stage_id", sa.UUID(), sa.ForeignKey("helpdesk_pipeline_stages.id"), nullable=True))
    op.create_index("ix_helpdesk_tickets_team", "helpdesk_tickets", ["team_id"])
    op.create_index("ix_helpdesk_tickets_stage", "helpdesk_tickets", ["pipeline_stage_id"])


def downgrade() -> None:
    op.drop_index("ix_helpdesk_tickets_stage", table_name="helpdesk_tickets")
    op.drop_index("ix_helpdesk_tickets_team", table_name="helpdesk_tickets")
    op.drop_column("helpdesk_tickets", "pipeline_stage_id")
    op.drop_column("helpdesk_tickets", "team_id")

"""127_helpdesk_teams_pipelines

Revision ID: 127_helpdesk_teams_pipelines
Revises: 126_project_revenue
Create Date: 2026-08-20

Helpdesk teams + customizable pipelines (Odoo-style).
"""
import sqlalchemy as sa
from alembic import op

revision = "127_helpdesk_teams_pipelines"
down_revision = "126_project_revenue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "helpdesk_teams",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lead_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_helpdesk_teams_company", "helpdesk_teams", ["company_id"])
    op.create_table(
        "helpdesk_team_members",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("team_id", sa.UUID(), sa.ForeignKey("helpdesk_teams.id"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_helpdesk_team_members_team", "helpdesk_team_members", ["team_id"])
    op.create_index("ix_helpdesk_team_members_user", "helpdesk_team_members", ["user_id"])
    op.create_table(
        "helpdesk_pipelines",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_helpdesk_pipelines_company", "helpdesk_pipelines", ["company_id"])
    op.create_table(
        "helpdesk_pipeline_stages",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("pipeline_id", sa.UUID(), sa.ForeignKey("helpdesk_pipelines.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_helpdesk_pipeline_stages_pipeline", "helpdesk_pipeline_stages", ["pipeline_id"])


def downgrade() -> None:
    op.drop_table("helpdesk_pipeline_stages")
    op.drop_table("helpdesk_pipelines")
    op.drop_table("helpdesk_team_members")
    op.drop_table("helpdesk_teams")

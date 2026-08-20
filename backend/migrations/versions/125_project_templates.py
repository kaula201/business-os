"""125_project_templates

Revision ID: 125_project_templates
Revises: 124_pos_fiscal_journal
Create Date: 2026-08-20

Project templates (milestones + tasks) for Odoo-style project setup.
"""
import sqlalchemy as sa
from alembic import op

revision = "125_project_templates"
down_revision = "124_pos_fiscal_journal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_templates",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_budget", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_project_templates_company", "project_templates", ["company_id"])
    op.create_table(
        "project_template_milestones",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("template_id", sa.UUID(), sa.ForeignKey("project_templates.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ptm_template", "project_template_milestones", ["template_id"])
    op.create_table(
        "project_template_tasks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("template_id", sa.UUID(), sa.ForeignKey("project_templates.id"), nullable=False),
        sa.Column("milestone_id", sa.UUID(), sa.ForeignKey("project_template_milestones.id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ptt_template", "project_template_tasks", ["template_id"])


def downgrade() -> None:
    op.drop_table("project_template_tasks")
    op.drop_table("project_template_milestones")
    op.drop_table("project_templates")

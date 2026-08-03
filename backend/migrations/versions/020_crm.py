"""Add tenant-scoped CRM leads, opportunities and activities.
Revision ID: 020_crm
Revises: 019_accounting_periods
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020_crm"
down_revision: Union[str, None] = "019_accounting_periods"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crm_leads",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("owner_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("converted_client_id", sa.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("source", sa.String(30), server_default="other", nullable=False),
        sa.Column("status", sa.String(30), server_default="new", nullable=False),
        sa.Column("estimated_value", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("converted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_crm_leads_company_status", "crm_leads", ["company_id", "status"])
    op.create_index("ix_crm_leads_owner", "crm_leads", ["company_id", "owner_id"])
    op.create_index("ix_crm_leads_created", "crm_leads", ["company_id", "created_at"])

    op.create_table(
        "crm_opportunities",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("lead_id", sa.UUID(as_uuid=True), sa.ForeignKey("crm_leads.id"), nullable=True),
        sa.Column("client_id", sa.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("owner_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("stage", sa.String(30), server_default="qualification", nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("probability", sa.Integer(), server_default="10", nullable=False),
        sa.Column("expected_close_date", sa.Date(), nullable=True),
        sa.Column("lost_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_crm_opportunity_amount_nonnegative"),
        sa.CheckConstraint("probability >= 0 AND probability <= 100", name="ck_crm_opportunity_probability"),
        sa.CheckConstraint("lead_id IS NOT NULL OR client_id IS NOT NULL", name="ck_crm_opportunity_related_party"),
    )
    op.create_index("ix_crm_opportunities_company_stage", "crm_opportunities", ["company_id", "stage"])
    op.create_index("ix_crm_opportunities_owner", "crm_opportunities", ["company_id", "owner_id"])
    op.create_index("ix_crm_opportunities_lead", "crm_opportunities", ["lead_id"])
    op.create_index("ix_crm_opportunities_client", "crm_opportunities", ["client_id"])

    op.create_table(
        "crm_activities",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("lead_id", sa.UUID(as_uuid=True), sa.ForeignKey("crm_leads.id"), nullable=True),
        sa.Column("opportunity_id", sa.UUID(as_uuid=True), sa.ForeignKey("crm_opportunities.id"), nullable=True),
        sa.Column("client_id", sa.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("assigned_to", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("activity_type", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="planned", nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "num_nonnulls(lead_id, opportunity_id, client_id) = 1",
            name="ck_crm_activity_one_target",
        ),
    )
    op.create_index("ix_crm_activities_company_status", "crm_activities", ["company_id", "status"])
    op.create_index("ix_crm_activities_due", "crm_activities", ["company_id", "due_at"])
    op.create_index("ix_crm_activities_lead", "crm_activities", ["lead_id"])
    op.create_index("ix_crm_activities_opportunity", "crm_activities", ["opportunity_id"])
    op.create_index("ix_crm_activities_client", "crm_activities", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_crm_activities_client", table_name="crm_activities")
    op.drop_index("ix_crm_activities_opportunity", table_name="crm_activities")
    op.drop_index("ix_crm_activities_lead", table_name="crm_activities")
    op.drop_index("ix_crm_activities_due", table_name="crm_activities")
    op.drop_index("ix_crm_activities_company_status", table_name="crm_activities")
    op.drop_table("crm_activities")
    op.drop_index("ix_crm_opportunities_client", table_name="crm_opportunities")
    op.drop_index("ix_crm_opportunities_lead", table_name="crm_opportunities")
    op.drop_index("ix_crm_opportunities_owner", table_name="crm_opportunities")
    op.drop_index("ix_crm_opportunities_company_stage", table_name="crm_opportunities")
    op.drop_table("crm_opportunities")
    op.drop_index("ix_crm_leads_created", table_name="crm_leads")
    op.drop_index("ix_crm_leads_owner", table_name="crm_leads")
    op.drop_index("ix_crm_leads_company_status", table_name="crm_leads")
    op.drop_table("crm_leads")

"""076_sales_teams

Revision ID: 076_sales_teams
Revises: 075_sales_tools
Create Date: 2026-08-11

Sales teams, members, targets, commission rules + accruals.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "076_sales_teams"
down_revision: str | None = "075_sales_tools"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_teams",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("manager_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "name", name="uq_sales_team_company_name"),
    )
    op.create_index("ix_sales_teams_company_id", "sales_teams", ["company_id"])

    op.create_table(
        "sales_team_members",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_teams.id"), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("team_id", "user_id", name="uq_sales_team_member"),
    )
    op.create_index("ix_sales_team_members_team_id", "sales_team_members", ["team_id"])
    op.create_index("ix_sales_team_members_user_id", "sales_team_members", ["user_id"])

    op.create_table(
        "sales_targets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("team_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_teams.id"), nullable=True),
        sa.Column("owner_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("target_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("achieved_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "period", "team_id", "owner_id", name="uq_sales_target_period"),
    )
    op.create_index("ix_sales_targets_company_id", "sales_targets", ["company_id"])
    op.create_index("ix_sales_targets_period", "sales_targets", ["period"])

    op.create_table(
        "commission_rules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("team_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_teams.id"), nullable=True),
        sa.Column("owner_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("product_category_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("rate_percent", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("fixed_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_commission_rules_company_id", "commission_rules", ["company_id"])

    op.create_table(
        "commission_accruals",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("rule_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("commission_rules.id"), nullable=False),
        sa.Column("order_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("owner_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("team_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_teams.id"), nullable=True),
        sa.Column("base_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="accrued"),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "rule_id", "order_id", name="uq_commission_rule_order"),
    )
    op.create_index("ix_commission_accruals_company_id", "commission_accruals", ["company_id"])
    op.create_index("ix_commission_accruals_rule_id", "commission_accruals", ["rule_id"])
    op.create_index("ix_commission_accruals_order_id", "commission_accruals", ["order_id"])
    op.create_index("ix_commission_accruals_status", "commission_accruals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_commission_accruals_status", table_name="commission_accruals")
    op.drop_index("ix_commission_accruals_order_id", table_name="commission_accruals")
    op.drop_index("ix_commission_accruals_rule_id", table_name="commission_accruals")
    op.drop_index("ix_commission_accruals_company_id", table_name="commission_accruals")
    op.drop_table("commission_accruals")
    op.drop_index("ix_commission_rules_company_id", table_name="commission_rules")
    op.drop_table("commission_rules")
    op.drop_index("ix_sales_targets_period", table_name="sales_targets")
    op.drop_index("ix_sales_targets_company_id", table_name="sales_targets")
    op.drop_table("sales_targets")
    op.drop_index("ix_sales_team_members_user_id", table_name="sales_team_members")
    op.drop_index("ix_sales_team_members_team_id", table_name="sales_team_members")
    op.drop_table("sales_team_members")
    op.drop_index("ix_sales_teams_company_id", table_name="sales_teams")
    op.drop_table("sales_teams")

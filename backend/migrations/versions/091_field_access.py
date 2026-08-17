"""091_field_access

Revision ID: 091_field_access
Revises: 090_security
Create Date: 2026-08-17

Field-level access rules.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "091_field_access"
down_revision = "090_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "field_access_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("field", sa.String(100), nullable=False),
        sa.Column("can_view", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_edit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_field_access_rules_company_id", "field_access_rules", ["company_id"])
    op.create_index("ix_field_access_rules_module", "field_access_rules", ["module"])


def downgrade() -> None:
    op.drop_table("field_access_rules")

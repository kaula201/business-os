"""094_accounting_controls

Revision ID: 094_accounting_controls
Revises: 093_automation
Create Date: 2026-08-17

Tenant-scoped fiscal positions, consolidation mappings and FX translation rates.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "094_accounting_controls"
down_revision = "093_automation"
branch_labels = None
depends_on = None

_POLICY = "company_id::text = current_setting('app.current_company_id', true)"


def _rls(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(f'CREATE POLICY "{table}_tenant_policy" ON "{table}" USING ({_POLICY}) WITH CHECK ({_POLICY})')


def upgrade() -> None:
    op.create_table(
        "fiscal_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("tax_type", sa.String(30), nullable=False, server_default="vat_standard"),
        sa.Column("vat_rate", sa.Numeric(7, 4), nullable=False, server_default="18.0000"),
        sa.Column("applies_to", sa.String(20), nullable=False, server_default="both"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "code", name="uq_fiscal_position_company_code"),
    )
    op.create_index("ix_fiscal_positions_company_id", "fiscal_positions", ["company_id"])

    op.create_table(
        "consolidation_account_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("source_account_code", sa.String(20), nullable=False),
        sa.Column("target_account_code", sa.String(20), nullable=False),
        sa.Column("target_name", sa.String(255), nullable=False),
        sa.Column("target_account_type", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "source_account_code", name="uq_consolidation_mapping_source"),
    )
    op.create_index("ix_consolidation_account_mappings_company_id", "consolidation_account_mappings", ["company_id"])

    op.create_table(
        "fx_translation_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("target_currency", sa.String(3), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("method", sa.String(20), nullable=False, server_default="closing"),
        sa.Column("source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "target_currency", "rate_date", "method", name="uq_fx_translation_rate"),
    )
    op.create_index("ix_fx_translation_rates_company_id", "fx_translation_rates", ["company_id"])

    for table in ("fiscal_positions", "consolidation_account_mappings", "fx_translation_rates"):
        _rls(table)


def downgrade() -> None:
    op.drop_table("fx_translation_rates")
    op.drop_table("consolidation_account_mappings")
    op.drop_table("fiscal_positions")

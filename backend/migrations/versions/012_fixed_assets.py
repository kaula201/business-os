"""Add fixed assets tables: fixed_assets, asset_depreciations.

Revision ID: 012_fixed_assets
Revises: 011_cash_register
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012_fixed_assets"
down_revision: Union[str, None] = "011_cash_register"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fixed_assets",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("purchase_cost", sa.Numeric(18, 2), nullable=False),
        sa.Column("useful_life_years", sa.Integer(), nullable=False),
        sa.Column("depreciation_method", sa.String(20), server_default=sa.text("'straight_line'"), nullable=False),
        sa.Column("salvage_value", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("accumulated_depreciation", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("book_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("last_depreciation_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("gl_account_id", sa.UUID(as_uuid=True), sa.ForeignKey("gl_accounts.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "asset_depreciations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("asset_id", sa.UUID(as_uuid=True), sa.ForeignKey("fixed_assets.id"), nullable=False, index=True),
        sa.Column("depreciation_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("period_label", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("asset_depreciations")
    op.drop_table("fixed_assets")

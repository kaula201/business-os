"""Add inventory_number, custodian, impairment, disposal to fixed_assets.

Revision ID: 033_assets_enhance
Revises: 032_budget_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033_assets_enhance"
down_revision: Union[str, None] = "032_budget_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("fixed_assets", sa.Column("inventory_number", sa.String(100), nullable=True))
    op.add_column("fixed_assets", sa.Column("custodian", sa.String(255), nullable=True))
    op.add_column("fixed_assets", sa.Column("impairment_amount", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False))
    op.add_column("fixed_assets", sa.Column("impairment_date", sa.Date(), nullable=True))
    op.add_column("fixed_assets", sa.Column("disposal_date", sa.Date(), nullable=True))
    op.add_column("fixed_assets", sa.Column("disposal_proceeds", sa.Numeric(18, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("fixed_assets", "disposal_proceeds")
    op.drop_column("fixed_assets", "disposal_date")
    op.drop_column("fixed_assets", "impairment_date")
    op.drop_column("fixed_assets", "impairment_amount")
    op.drop_column("fixed_assets", "custodian")
    op.drop_column("fixed_assets", "inventory_number")

"""Add opening_balance, responsible_person to cash_accounts.

Revision ID: 030_cash_enhance
Revises: 029_project_integration
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030_cash_enhance"
down_revision: Union[str, None] = "029_project_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cash_accounts", sa.Column("opening_balance", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False))
    op.add_column("cash_accounts", sa.Column("responsible_person", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("cash_accounts", "responsible_person")
    op.drop_column("cash_accounts", "opening_balance")

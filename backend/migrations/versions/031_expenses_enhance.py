"""Add project_id, tax_type, tax_amount to expenses.

Revision ID: 031_expenses_enhance
Revises: 030_cash_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "031_expenses_enhance"
down_revision: Union[str, None] = "030_cash_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_expenses_project", "expenses", "projects", ["project_id"], ["id"])
    op.add_column("expenses", sa.Column("tax_type", sa.String(30), nullable=True))
    op.add_column("expenses", sa.Column("tax_amount", sa.Numeric(18, 2), nullable=True))


def downgrade() -> None:
    op.drop_constraint("fk_expenses_project", "expenses", type_="foreignkey")
    op.drop_column("expenses", "project_id")
    op.drop_column("expenses", "tax_type")
    op.drop_column("expenses", "tax_amount")

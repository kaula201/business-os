"""Add scenario to budget_plans.

Revision ID: 032_budget_enhance
Revises: 031_expenses_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "032_budget_enhance"
down_revision: Union[str, None] = "031_expenses_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("budget_plans", sa.Column("scenario", sa.String(50), server_default="base", nullable=False))


def downgrade() -> None:
    op.drop_column("budget_plans", "scenario")

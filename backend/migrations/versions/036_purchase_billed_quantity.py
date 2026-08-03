"""Add billed_quantity to purchase_order_items for three-way matching.

Revision ID: 036_purchase_billed_quantity
Revises: 035_projects_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036_purchase_billed_quantity"
down_revision: Union[str, None] = "035_projects_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "purchase_order_items",
        sa.Column(
            "billed_quantity",
            sa.Numeric(18, 3),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("purchase_order_items", "billed_quantity")

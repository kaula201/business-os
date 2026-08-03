"""Enhance Orders module: payment tracking, vat_rate, lifecycle status.

Adds payment_status, paid_amount, payment_due_date, paid_at, vat_rate
columns to orders table. Renames default status from 'new' to 'draft'.

Revision ID: 043_orders_enhance
Revises: 042_crm_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "043_orders_enhance"
down_revision: Union[str, None] = "042_crm_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns
    op.add_column(
        "orders",
        sa.Column("vat_rate", sa.Float(), server_default="0.18", nullable=False),
    )
    op.add_column(
        "orders",
        sa.Column("payment_status", sa.String(20), server_default="unpaid", nullable=False),
    )
    op.add_column(
        "orders",
        sa.Column("paid_amount", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "orders",
        sa.Column("payment_due_date", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("paid_at", sa.DateTime(), nullable=True),
    )

    # Update existing 'new' status to 'draft'
    op.execute("UPDATE orders SET status = 'draft' WHERE status = 'new'")

    # Update default for new rows
    op.alter_column(
        "orders",
        "status",
        server_default="draft",
    )


def downgrade() -> None:
    op.drop_column("orders", "paid_at")
    op.drop_column("orders", "payment_due_date")
    op.drop_column("orders", "paid_amount")
    op.drop_column("orders", "payment_status")
    op.drop_column("orders", "vat_rate")

    # Revert default
    op.alter_column(
        "orders",
        "status",
        server_default="new",
    )
    op.execute("UPDATE orders SET status = 'new' WHERE status = 'draft'")

"""Create POS tables: pos_sessions, pos_orders, pos_order_items.

Revision ID: 027_pos
Revises: 026_projects
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027_pos"
down_revision: Union[str, None] = "026_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pos_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("opened_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("opened_by", sa.UUID(), nullable=True),
        sa.Column("total_sales", sa.Numeric(18, 2), server_default="0"),
        sa.Column("total_orders", sa.Integer(), server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_sessions_company", "pos_sessions", ["company_id"])

    op.create_table(
        "pos_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="completed"),
        sa.Column("subtotal", sa.Numeric(18, 2), server_default="0"),
        sa.Column("vat_amount", sa.Numeric(18, 2), server_default="0"),
        sa.Column("total", sa.Numeric(18, 2), server_default="0"),
        sa.Column("payment_method", sa.String(50), server_default="cash"),
        sa.Column("payment_reference", sa.String(100), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["pos_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_orders_company", "pos_orders", ["company_id"])
    op.create_index("ix_pos_orders_session", "pos_orders", ["session_id"])

    op.create_table(
        "pos_order_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pos_order_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.ForeignKeyConstraint(["pos_order_id"], ["pos_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_order_items_order", "pos_order_items", ["pos_order_id"])


def downgrade() -> None:
    op.drop_table("pos_order_items")
    op.drop_table("pos_orders")
    op.drop_table("pos_sessions")

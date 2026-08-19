"""112_pos_restaurant

Revision ID: 112_pos_restaurant
Revises: 111_pos_extended
Create Date: 2026-08-19

Restaurant tables, order types and self-ordering sessions.
"""
import sqlalchemy as sa
from alembic import op

revision = "112_pos_restaurant"
down_revision = "111_pos_extended"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "restaurant_tables",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("status", sa.String(20), nullable=False, server_default="free"),
        sa.Column("current_order_id", sa.UUID(), sa.ForeignKey("pos_orders.id"), nullable=True),
        sa.Column("qr_code", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_restaurant_tables_company", "restaurant_tables", ["company_id"])

    op.create_table(
        "pos_order_types",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pos_order_types_company", "pos_order_types", ["company_id"])

    op.create_table(
        "self_order_sessions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("table_id", sa.UUID(), sa.ForeignKey("restaurant_tables.id"), nullable=True),
        sa.Column("token", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("order_id", sa.UUID(), sa.ForeignKey("pos_orders.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_self_order_sessions_company", "self_order_sessions", ["company_id"])
    op.create_index("ix_self_order_sessions_token", "self_order_sessions", ["token"])


def downgrade() -> None:
    op.drop_table("self_order_sessions")
    op.drop_table("pos_order_types")
    op.drop_table("restaurant_tables")

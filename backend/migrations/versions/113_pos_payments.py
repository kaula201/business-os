"""113_pos_payments

Revision ID: 113_pos_payments
Revises: 112_pos_restaurant
Create Date: 2026-08-19

Split payments for POS orders.
"""
import sqlalchemy as sa
from alembic import op

revision = "113_pos_payments"
down_revision = "112_pos_restaurant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_payments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("order_id", sa.UUID(), sa.ForeignKey("pos_orders.id"), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("gift_card_id", sa.UUID(), sa.ForeignKey("gift_cards.id"), nullable=True),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pos_payments_company", "pos_payments", ["company_id"])
    op.create_index("ix_pos_payments_order", "pos_payments", ["order_id"])


def downgrade() -> None:
    op.drop_table("pos_payments")

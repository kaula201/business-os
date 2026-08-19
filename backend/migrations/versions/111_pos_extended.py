"""111_pos_extended

Revision ID: 111_pos_extended
Revises: 110_exchange_diff_balance_scope
Create Date: 2026-08-19

Gift cards, cash register movements and Z-reports for POS.
"""
import sqlalchemy as sa
from alembic import op

revision = "111_pos_extended"
down_revision = "110_exchange_diff_balance_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gift_cards",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("card_number", sa.String(50), nullable=False, unique=True),
        sa.Column("pin", sa.String(10), nullable=True),
        sa.Column("initial_balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("issued_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_gift_cards_company", "gift_cards", ["company_id"])
    op.create_index("ix_gift_cards_number", "gift_cards", ["card_number"])

    op.create_table(
        "gift_card_transactions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("card_id", sa.UUID(), sa.ForeignKey("gift_cards.id"), nullable=False),
        sa.Column("order_id", sa.UUID(), sa.ForeignKey("pos_orders.id"), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_gift_card_tx_company", "gift_card_transactions", ["company_id"])
    op.create_index("ix_gift_card_tx_card", "gift_card_transactions", ["card_id"])

    op.create_table(
        "pos_cash_movements",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("pos_sessions.id"), nullable=False),
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pos_cash_movements_company", "pos_cash_movements", ["company_id"])
    op.create_index("ix_pos_cash_movements_session", "pos_cash_movements", ["session_id"])

    op.create_table(
        "pos_z_reports",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("pos_sessions.id"), nullable=False),
        sa.Column("report_number", sa.String(50), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=False),
        sa.Column("total_sales", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_orders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_refunds", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cash_in", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cash_out", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("expected_cash", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("declared_cash", sa.Numeric(18, 2), nullable=True),
        sa.Column("difference", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pos_z_reports_company", "pos_z_reports", ["company_id"])
    op.create_index("ix_pos_z_reports_session", "pos_z_reports", ["session_id"])


def downgrade() -> None:
    op.drop_table("pos_z_reports")
    op.drop_table("pos_cash_movements")
    op.drop_table("gift_card_transactions")
    op.drop_table("gift_cards")

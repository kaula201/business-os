"""124_pos_fiscal_journal

Revision ID: 124_pos_fiscal_journal
Revises: 123_pos_device_network
Create Date: 2026-08-20

Fiscal memory (software equivalent) — hash-chained journal.
"""
import sqlalchemy as sa
from alembic import op

revision = "124_pos_fiscal_journal"
down_revision = "123_pos_device_network"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_fiscal_journal",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("order_id", sa.UUID(), sa.ForeignKey("pos_orders.id"), nullable=False),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GEL"),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("block_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pos_fiscal_journal_company", "pos_fiscal_journal", ["company_id"])
    op.create_index("ix_pos_fiscal_journal_order", "pos_fiscal_journal", ["order_id"])


def downgrade() -> None:
    op.drop_table("pos_fiscal_journal")

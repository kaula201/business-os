"""081_pos_enhanced

Revision ID: 081_pos_enhanced
Revises: 080_procurement
Create Date: 2026-08-14

POS: refunds, loyalty accounts/transactions, offline queue, fiscal devices.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "081_pos_enhanced"
down_revision: str | None = "080_procurement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_refunds",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("order_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("pos_orders.id"), nullable=False),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("pos_sessions.id"), nullable=False),
        sa.Column("refund_number", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pos_refunds_company_id", "pos_refunds", ["company_id"])
    op.create_index("ix_pos_refunds_order_id", "pos_refunds", ["order_id"])

    op.create_table(
        "pos_loyalty_accounts",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("client_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("points", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_earned", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_redeemed", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pos_loyalty_accounts_company_id", "pos_loyalty_accounts", ["company_id"])
    op.create_index("ix_pos_loyalty_accounts_client_id", "pos_loyalty_accounts", ["client_id"])

    op.create_table(
        "pos_loyalty_transactions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("account_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("pos_loyalty_accounts.id"), nullable=False),
        sa.Column("order_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("pos_orders.id"), nullable=True),
        sa.Column("points", sa.Numeric(12, 2), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pos_loyalty_transactions_company_id", "pos_loyalty_transactions", ["company_id"])
    op.create_index("ix_pos_loyalty_transactions_account_id", "pos_loyalty_transactions", ["account_id"])

    op.create_table(
        "pos_offline_queue",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("device_id", sa.String(100), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_pos_offline_queue_company_id", "pos_offline_queue", ["company_id"])
    op.create_index("ix_pos_offline_queue_device_id", "pos_offline_queue", ["device_id"])

    op.create_table(
        "pos_fiscal_devices",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("device_type", sa.String(30), nullable=False, server_default="fiscal_printer"),
        sa.Column("serial_number", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pos_fiscal_devices_company_id", "pos_fiscal_devices", ["company_id"])


def downgrade() -> None:
    op.drop_table("pos_fiscal_devices")
    op.drop_table("pos_offline_queue")
    op.drop_table("pos_loyalty_transactions")
    op.drop_table("pos_loyalty_accounts")
    op.drop_table("pos_refunds")

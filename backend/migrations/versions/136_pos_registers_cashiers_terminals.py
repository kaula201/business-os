"""136_pos_registers_cashiers_terminals

Revision ID: 136_pos_registers_cashiers_terminals
Revises: 135_payslip_explanation
Create Date: 2026-08-24

POS registers (cash journals), cashiers (PIN login), payment terminals (TBC/BOG).
"""
import sqlalchemy as sa
from alembic import op

revision = "136_pos_registers_cashiers_terminals"
down_revision = "135_payslip_explanation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_registers",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("cash_journal_id", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pos_registers_company", "pos_registers", ["company_id"])

    op.create_table(
        "pos_cashiers",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pin_hash", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pos_cashiers_company", "pos_cashiers", ["company_id"])

    op.create_table(
        "pos_payment_terminals",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("terminal_id", sa.String(100), nullable=False),
        sa.Column("merchant_id", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pos_payment_terminals_company", "pos_payment_terminals", ["company_id"])


def downgrade() -> None:
    op.drop_table("pos_payment_terminals")
    op.drop_table("pos_cashiers")
    op.drop_table("pos_registers")

"""Enhance Suppliers module: rating, bank details, rating history, purchase stats.

Adds columns to suppliers table (rating, total_purchase_amount, last_purchase_date)
and creates supplier_bank_details and supplier_rating_history tables.

Revision ID: 037_supplier_enhance
Revises: 036_purchase_billed_quantity
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "037_supplier_enhance"
down_revision: Union[str, None] = "036_purchase_billed_quantity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Supplier table enhancements ───────────────────────────────────
    op.add_column(
        "suppliers",
        sa.Column("rating", sa.Float(), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column(
            "total_purchase_amount",
            sa.Numeric(18, 2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "suppliers",
        sa.Column("last_purchase_date", sa.Date(), nullable=True),
    )

    # ── Supplier bank details table ───────────────────────────────────
    op.create_table(
        "supplier_bank_details",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=False, index=True),
        sa.Column("bank_name", sa.String(150), nullable=False),
        sa.Column("account_name", sa.String(150), nullable=False),
        sa.Column("iban", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(3), server_default=sa.text("'GEL'"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "supplier_id", "iban", name="uq_supplier_bank_iban"
        ),
    )

    # ── Supplier rating history table ─────────────────────────────────
    op.create_table(
        "supplier_rating_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=False, index=True),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("supplier_rating_history")
    op.drop_table("supplier_bank_details")
    op.drop_column("suppliers", "last_purchase_date")
    op.drop_column("suppliers", "total_purchase_amount")
    op.drop_column("suppliers", "rating")

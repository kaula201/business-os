"""Create contracts table.

Revision ID: 051_contracts
Revises: 050_approvals
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "051_contracts"
down_revision: Union[str, None] = "050_approvals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contracts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False, index=True),
        sa.Column("counterparty", sa.String(255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("value", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False, index=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("contracts")

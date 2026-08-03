"""Create leaves table.

Revision ID: 052_leaves
Revises: 051_contracts

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "052_leaves"
down_revision: Union[str, None] = "051_contracts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leaves",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("employee_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("leave_type", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_leaves_company_id", "leaves", ["company_id"])
    op.create_index("ix_leaves_employee_id", "leaves", ["employee_id"])
    op.create_index("ix_leaves_leave_type", "leaves", ["leave_type"])
    op.create_index("ix_leaves_status", "leaves", ["status"])


def downgrade() -> None:
    op.drop_index("ix_leaves_status", table_name="leaves")
    op.drop_index("ix_leaves_leave_type", table_name="leaves")
    op.drop_index("ix_leaves_employee_id", table_name="leaves")
    op.drop_index("ix_leaves_company_id", table_name="leaves")
    op.drop_table("leaves")

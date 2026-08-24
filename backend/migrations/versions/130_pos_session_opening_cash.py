"""130_pos_session_opening_cash

Revision ID: 130_pos_session_opening_cash
Revises: 129_api_keys_extend
Create Date: 2026-08-20

Opening cash on POS sessions (cashier + register context).
"""
import sqlalchemy as sa
from alembic import op

revision = "130_pos_session_opening_cash"
down_revision = "129_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_sessions", sa.Column("opening_cash", sa.Numeric(18, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("pos_sessions", "opening_cash")

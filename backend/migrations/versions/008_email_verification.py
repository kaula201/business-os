"""Add email_verified and email_verification_token columns to users table.

Revision ID: 008_email_verification
Revises: 007_gl_foundation
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_email_verification"
down_revision: Union[str, None] = "007_gl_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("email_verification_token", sa.String(500), nullable=True))
    op.create_index("ix_users_email_verification_token", "users", ["email_verification_token"])


def downgrade() -> None:
    op.drop_index("ix_users_email_verification_token", table_name="users")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "email_verified")

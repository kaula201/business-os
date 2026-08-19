"""109_vendor_portal_auth

Revision ID: 109_vendor_portal_auth
Revises: 108_vendor_portal
Create Date: 2026-08-19

Add hashed_password to vendor_portal_users for supplier self-service login.
"""
from alembic import op
import sqlalchemy as sa

revision = "109_vendor_portal_auth"
down_revision = "108_vendor_portal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vendor_portal_users", sa.Column("hashed_password", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("vendor_portal_users", "hashed_password")

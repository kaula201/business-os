"""123_pos_device_network

Revision ID: 123_pos_device_network
Revises: 122_pos_restaurant_courses_floorplan
Create Date: 2026-08-20

Network printing fields on POS fiscal devices (IP + port 9100).
"""
import sqlalchemy as sa
from alembic import op

revision = "123_pos_device_network"
down_revision = "122_pos_restaurant_courses_floorplan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_fiscal_devices", sa.Column("ip_address", sa.String(45), nullable=True))
    op.add_column("pos_fiscal_devices", sa.Column("port", sa.Integer(), nullable=False, server_default="9100"))


def downgrade() -> None:
    op.drop_column("pos_fiscal_devices", "port")
    op.drop_column("pos_fiscal_devices", "ip_address")

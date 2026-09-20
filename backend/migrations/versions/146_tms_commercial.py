"""146_tms_commercial

Revision ID: 146_tms_commercial
Revises: 145_tms_fuel
Create Date: 2026-09-21

Standalone-sale TMS enhancements: delivery-request dropoff coordinates for
route planning (no geocoder dependency).
"""
import sqlalchemy as sa
from alembic import op

revision = "146_tms_commercial"
down_revision = "145_tms_fuel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tms_delivery_requests", sa.Column("dropoff_lat", sa.Numeric(9, 6), nullable=True))
    op.add_column("tms_delivery_requests", sa.Column("dropoff_lng", sa.Numeric(9, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("tms_delivery_requests", "dropoff_lng")
    op.drop_column("tms_delivery_requests", "dropoff_lat")

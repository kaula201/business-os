"""Add map locations to fleet vehicles.

Revision ID: 021_fleet_vehicle_locations
Revises: 020_crm
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021_fleet_vehicle_locations"
down_revision: Union[str, None] = "020_crm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vehicles", sa.Column("location_name", sa.String(length=255), nullable=True))
    op.add_column("vehicles", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("vehicles", sa.Column("longitude", sa.Numeric(10, 6), nullable=True))
    op.create_check_constraint("ck_vehicle_latitude", "vehicles", "latitude IS NULL OR latitude BETWEEN -90 AND 90")
    op.create_check_constraint("ck_vehicle_longitude", "vehicles", "longitude IS NULL OR longitude BETWEEN -180 AND 180")
    op.create_check_constraint(
        "ck_vehicle_coordinate_pair",
        "vehicles",
        "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_vehicle_coordinate_pair", "vehicles", type_="check")
    op.drop_constraint("ck_vehicle_longitude", "vehicles", type_="check")
    op.drop_constraint("ck_vehicle_latitude", "vehicles", type_="check")
    op.drop_column("vehicles", "longitude")
    op.drop_column("vehicles", "latitude")
    op.drop_column("vehicles", "location_name")
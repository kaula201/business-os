"""Enhance fleet: odometer readings, service intervals, tank capacity.

Revision ID: 047_fleet_enhance
Revises: 046_reports
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "047_fleet_enhance"
down_revision: Union[str, None] = "046_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Vehicle columns for service intervals + tank capacity
    op.add_column("vehicles", sa.Column("tank_capacity_liters", sa.Numeric(8, 2), nullable=True))
    op.add_column("vehicles", sa.Column("service_interval_km", sa.Numeric(10, 1), nullable=True))
    op.add_column("vehicles", sa.Column("service_interval_days", sa.Integer(), nullable=True))

    # OdometerReading table
    op.create_table(
        "odometer_readings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("reading_date", sa.Date(), nullable=False),
        sa.Column("mileage_km", sa.Numeric(10, 1), nullable=False),
        sa.Column("source", sa.String(30), server_default="manual", nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("mileage_km >= 0", name="ck_odometer_mileage_nonneg"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_odometer_readings_vehicle", "odometer_readings", ["vehicle_id"])


def downgrade() -> None:
    op.drop_table("odometer_readings")
    op.drop_column("vehicles", "service_interval_days")
    op.drop_column("vehicles", "service_interval_km")
    op.drop_column("vehicles", "tank_capacity_liters")

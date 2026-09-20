"""147_tms_gps

Revision ID: 147_tms_gps
Revises: 146_tms_commercial
Create Date: 2026-09-21

REQ-TMS-04 live tracking: GPS telemetry feed for active trips + circular
geofences around stops for auto-arrival.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "147_tms_gps"
down_revision = "146_tms_commercial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tms_trip_telemetry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("tms_trips.id"), nullable=False),
        sa.Column("device_id", sa.String(64), nullable=True),
        sa.Column("tracked_at", sa.DateTime(), nullable=False),
        sa.Column("lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("lng", sa.Numeric(9, 6), nullable=False),
        sa.Column("speed_kmh", sa.Numeric(6, 1), nullable=True),
        sa.Column("heading", sa.Numeric(5, 1), nullable=True),
        sa.Column("server_received_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tms_trip_telemetry_trip", "tms_trip_telemetry", ["trip_id", "tracked_at"])

    op.create_table(
        "tms_trip_geofences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("tms_trips.id"), nullable=False),
        sa.Column("stop_id", UUID(as_uuid=True), sa.ForeignKey("tms_trip_stops.id"), nullable=False),
        sa.Column("lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("lng", sa.Numeric(9, 6), nullable=False),
        sa.Column("radius_m", sa.Numeric(8, 1), nullable=False, server_default="500"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "trip_id", "stop_id", name="uq_tms_trip_geofence_stop"),
    )


def downgrade() -> None:
    op.drop_table("tms_trip_geofences")
    op.drop_index("ix_tms_trip_telemetry_trip", table_name="tms_trip_telemetry")
    op.drop_table("tms_trip_telemetry")

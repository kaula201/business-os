"""145_tms_fuel

Revision ID: 145_tms_fuel
Revises: 144_tms_2
Create Date: 2026-09-21

REQ-TMS-07: link fuel logs to an optional trip for per-trip cost/consumption
reporting.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "145_tms_fuel"
down_revision = "144_tms_2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fuel_logs", sa.Column("trip_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_fuel_logs_trip", "fuel_logs", "tms_trips", ["trip_id"], ["id"])
    op.create_index("ix_fuel_logs_trip", "fuel_logs", ["trip_id"])


def downgrade() -> None:
    op.drop_index("ix_fuel_logs_trip", table_name="fuel_logs")
    op.drop_constraint("fk_fuel_logs_trip", "fuel_logs", type_="foreignkey")
    op.drop_column("fuel_logs", "trip_id")

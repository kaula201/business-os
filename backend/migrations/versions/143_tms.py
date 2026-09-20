"""143_tms

Revision ID: 143_tms
Revises: 142_metric_definition
Create Date: 2026-09-21

TMS 2.0 (REQ-TMS-01..09): driver, delivery requests, trips, stops, loads,
POD, cost allocation. Adds cargo capacity/ownership columns to vehicles.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "143_tms"
down_revision = "142_metric_definition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Vehicle capacity / ownership (REQ-TMS-02/09)
    op.add_column("vehicles", sa.Column("capacity_kg", sa.Numeric(12, 2), nullable=True))
    op.add_column("vehicles", sa.Column("capacity_m3", sa.Numeric(12, 2), nullable=True))
    op.add_column("vehicles", sa.Column("ownership", sa.String(20), nullable=False, server_default="own"))
    op.add_column("vehicles", sa.Column("maintenance_due_date", sa.Date(), nullable=True))

    # Drivers
    op.create_table(
        "tms_drivers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("license_number", sa.String(50), nullable=True),
        sa.Column("license_categories", sa.String(100), nullable=True),
        sa.Column("license_valid_until", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tms_drivers_company", "tms_drivers", ["company_id"])

    # Delivery requests (REQ-TMS-01)
    op.create_table(
        "tms_delivery_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("request_number", sa.String(50), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("pickup_address", sa.String(500), nullable=True),
        sa.Column("dropoff_address", sa.String(500), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("scheduled_from", sa.DateTime(), nullable=True),
        sa.Column("scheduled_to", sa.DateTime(), nullable=True),
        sa.Column("weight_kg", sa.Numeric(14, 3), nullable=True),
        sa.Column("volume_m3", sa.Numeric(14, 3), nullable=True),
        sa.Column("package_count", sa.Integer(), nullable=True),
        sa.Column("special_conditions", sa.Text(), nullable=True),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_qty", sa.Numeric(14, 3), nullable=True),
        sa.Column("exception", sa.String(255), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "request_number", name="uq_tms_delivery_request_number"),
    )
    op.create_index("ix_tms_delivery_requests_company", "tms_delivery_requests", ["company_id"])
    op.create_index("ix_tms_delivery_requests_source", "tms_delivery_requests", ["source_type", "source_id"])

    # Trips (REQ-TMS-02)
    op.create_table(
        "tms_trips",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trip_number", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("vehicle_id", UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("driver_id", UUID(as_uuid=True), sa.ForeignKey("tms_drivers.id"), nullable=True),
        sa.Column("carrier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("carrier_rate", sa.Numeric(14, 2), nullable=True),
        sa.Column("planned_start", sa.DateTime(), nullable=True),
        sa.Column("planned_end", sa.DateTime(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("total_weight_kg", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("total_volume_m3", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "trip_number", name="uq_tms_trip_number"),
    )
    op.create_index("ix_tms_trips_company", "tms_trips", ["company_id"])
    op.create_index("ix_tms_trips_vehicle", "tms_trips", ["vehicle_id"])

    # Stops
    op.create_table(
        "tms_trip_stops",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("tms_trips.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("window_from", sa.DateTime(), nullable=True),
        sa.Column("window_to", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("arrived_at", sa.DateTime(), nullable=True),
        sa.Column("departed_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_qty", sa.Numeric(14, 3), nullable=True),
        sa.Column("exception", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tms_trip_stops_trip", "tms_trip_stops", ["trip_id", "sequence"])

    # Loads
    op.create_table(
        "tms_trip_loads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("tms_trips.id"), nullable=False),
        sa.Column("stop_id", UUID(as_uuid=True), sa.ForeignKey("tms_trip_stops.id"), nullable=True),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("tms_delivery_requests.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("weight_kg", sa.Numeric(14, 3), nullable=True),
        sa.Column("volume_m3", sa.Numeric(14, 3), nullable=True),
        sa.UniqueConstraint("company_id", "trip_id", "delivery_id", name="uq_tms_trip_load_delivery"),
    )
    op.create_index("ix_tms_trip_loads_trip", "tms_trip_loads", ["trip_id"])

    # POD (REQ-TMS-05/06)
    op.create_table(
        "tms_pods",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("tms_trips.id"), nullable=False),
        sa.Column("stop_id", UUID(as_uuid=True), sa.ForeignKey("tms_trip_stops.id"), nullable=False),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("tms_delivery_requests.id"), nullable=True),
        sa.Column("delivered_qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=False),
        sa.Column("recipient_name", sa.String(255), nullable=True),
        sa.Column("exception", sa.String(100), nullable=True),
        sa.Column("exception_reason", sa.Text(), nullable=True),
        sa.Column("evidence_id", UUID(as_uuid=True), nullable=True),
        sa.Column("corrected_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("corrected_at", sa.DateTime(), nullable=True),
        sa.Column("device_event_id", sa.String(64), nullable=True),
        sa.Column("device_time", sa.DateTime(), nullable=True),
        sa.Column("server_received_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tms_pods_trip", "tms_pods", ["trip_id", "delivery_id"])

    # Cost allocation (REQ-TMS-08)
    op.create_table(
        "tms_trip_cost_allocations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("tms_trips.id"), nullable=False),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("tms_delivery_requests.id"), nullable=False),
        sa.Column("cost_type", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("allocation_method", sa.String(20), nullable=False, server_default="weight"),
        sa.Column("source_expense_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "trip_id", "delivery_id", "cost_type", name="uq_tms_trip_cost_alloc"),
    )
    op.create_index("ix_tms_trip_cost_alloc_trip", "tms_trip_cost_allocations", ["trip_id"])


def downgrade() -> None:
    op.drop_table("tms_trip_cost_allocations")
    op.drop_table("tms_pods")
    op.drop_table("tms_trip_loads")
    op.drop_table("tms_trip_stops")
    op.drop_table("tms_trips")
    op.drop_table("tms_delivery_requests")
    op.drop_table("tms_drivers")
    op.drop_column("vehicles", "capacity_kg")
    op.drop_column("vehicles", "capacity_m3")
    op.drop_column("vehicles", "ownership")
    op.drop_column("vehicles", "maintenance_due_date")

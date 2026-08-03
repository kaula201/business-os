"""Add fleet management tables: vehicles, fuel_logs, service_records, driver_assignments.

Revision ID: 010_fleet_management
Revises: 009_pgvector_rag
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_fleet_management"
down_revision: Union[str, None] = "009_pgvector_rag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("plate_number", sa.String(20), nullable=False, index=True),
        sa.Column("brand", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("year", sa.Numeric(4, 0), nullable=True),
        sa.Column("vin", sa.String(50), nullable=True),
        sa.Column("color", sa.String(50), nullable=True),
        sa.Column("fuel_type", sa.String(20), server_default=sa.text("'petrol'"), nullable=False),
        sa.Column("engine_capacity", sa.Numeric(6, 1), nullable=True),
        sa.Column("initial_mileage", sa.Numeric(10, 1), server_default=sa.text("0"), nullable=False),
        sa.Column("current_mileage", sa.Numeric(10, 1), server_default=sa.text("0"), nullable=False),
        sa.Column("insurance_company", sa.String(255), nullable=True),
        sa.Column("insurance_policy", sa.String(100), nullable=True),
        sa.Column("insurance_valid_until", sa.Date(), nullable=True),
        sa.Column("tech_inspection_until", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_vehicles_company_id", "vehicles", ["company_id"])

    op.create_table(
        "fuel_logs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("vehicle_id", sa.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("refuel_date", sa.Date(), nullable=False),
        sa.Column("liters", sa.Numeric(10, 2), nullable=False),
        sa.Column("price_per_liter", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("mileage_at_refuel", sa.Numeric(10, 1), nullable=False),
        sa.Column("fuel_card", sa.String(100), nullable=True),
        sa.Column("station", sa.String(255), nullable=True),
        sa.Column("receipt_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fuel_logs_vehicle_id", "fuel_logs", ["vehicle_id"])
    op.create_index("ix_fuel_logs_company_id", "fuel_logs", ["company_id"])

    op.create_table(
        "service_records",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("vehicle_id", sa.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("service_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mileage_at_service", sa.Numeric(10, 1), nullable=False),
        sa.Column("cost", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("service_provider", sa.String(255), nullable=True),
        sa.Column("invoice_number", sa.String(100), nullable=True),
        sa.Column("next_service_mileage", sa.Numeric(10, 1), nullable=True),
        sa.Column("next_service_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_service_records_vehicle_id", "service_records", ["vehicle_id"])
    op.create_index("ix_service_records_company_id", "service_records", ["company_id"])

    op.create_table(
        "driver_assignments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("vehicle_id", sa.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("driver_name", sa.String(255), nullable=False),
        sa.Column("driver_phone", sa.String(50), nullable=True),
        sa.Column("driver_license", sa.String(50), nullable=True),
        sa.Column("assigned_from", sa.Date(), nullable=False),
        sa.Column("assigned_until", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_driver_assignments_vehicle_id", "driver_assignments", ["vehicle_id"])
    op.create_index("ix_driver_assignments_company_id", "driver_assignments", ["company_id"])


def downgrade() -> None:
    op.drop_table("driver_assignments")
    op.drop_table("service_records")
    op.drop_table("fuel_logs")
    op.drop_table("vehicles")

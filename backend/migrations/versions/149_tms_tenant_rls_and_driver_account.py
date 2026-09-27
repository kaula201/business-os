"""149_tms_tenant_rls_and_driver_account

Revision ID: 149_tms_tenant_rls_and_driver_account
Revises: 148_tms_freight_invoice
Create Date: 2026-09-27

Standalone-sell hardening for TMS:
1. Row-Level Security (FORCE) on every tms_* table so a tenant is isolated at
   the DB layer, not only at the endpoint layer. The policy follows the same
   app.current_company_id convention as the rest of the ERP (migrations 062+).
2. tms_drivers.user_id — links a driver record to a User account so drivers can
   log into the PWA and be scoped to their own trips.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "149_tms_tenant_rls_and_driver_account"
down_revision = "148_tms_freight_invoice"
branch_labels = None
depends_on = None

TMS_TABLES = [
    "tms_drivers",
    "tms_delivery_requests",
    "tms_trips",
    "tms_trip_stops",
    "tms_trip_loads",
    "tms_pods",
    "tms_trip_cost_allocations",
    "tms_trip_telemetry",
    "tms_trip_geofences",
    "tms_freight_invoices",
]

# Same policy text as the established tenant RLS (062_rls_tenant_isolation).
POLICY = (
    "current_setting('app.current_company_id', true) IS NULL "
    "OR current_setting('app.current_company_id', true) = '' "
    "OR company_id::text = current_setting('app.current_company_id', true)"
)


def upgrade() -> None:
    # 1. driver account link
    op.add_column("tms_drivers", sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))
    op.create_index("ix_tms_drivers_user", "tms_drivers", ["user_id"])

    # 2. tenant RLS on every TMS table
    for table in TMS_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'CREATE POLICY "{table}_tenant_policy" ON "{table}" USING ({POLICY}) WITH CHECK ({POLICY})')


def downgrade() -> None:
    for table in TMS_TABLES:
        op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_policy" ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_tms_drivers_user", table_name="tms_drivers")
    op.drop_column("tms_drivers", "user_id")

"""144_tms_2

Revision ID: 144_tms_2
Revises: 143_tms
Create Date: 2026-09-21

TMS 2.0 completion (REQ-TMS-06/08): the closed set of gaps that move TMS from
partial to a full spec match —
- POD correction: supersedes_id preserves the original POD (REQ-TMS-06)
- cost allocation: version stamps the allocation rule (REQ-TMS-08)
- returned cargo: delivery request stamps a WMS return so failed/undelivered
  cargo only re-enters stock via WMS return (REQ-TMS-06)
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "144_tms_2"
down_revision = "143_tms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # POD correction chain (original preserved)
    op.add_column("tms_pods", sa.Column("supersedes_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_tms_pods_supersedes", "tms_pods", "tms_pods", ["supersedes_id"], ["id"])
    op.create_index("ix_tms_pods_supersedes", "tms_pods", ["supersedes_id"])

    # cost allocation rule version
    op.add_column("tms_trip_cost_allocations", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    # returned cargo → WMS return stamps
    op.add_column("tms_delivery_requests", sa.Column("returned_to_warehouse", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("tms_delivery_requests", sa.Column("returned_warehouse_id", UUID(as_uuid=True), nullable=True))
    op.add_column("tms_delivery_requests", sa.Column("returned_at", sa.DateTime(), nullable=True))
    op.create_foreign_key("fk_tms_delivery_return_wh", "tms_delivery_requests", "warehouses", ["returned_warehouse_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_tms_delivery_return_wh", "tms_delivery_requests", type_="foreignkey")
    op.drop_column("tms_delivery_requests", "returned_at")
    op.drop_column("tms_delivery_requests", "returned_warehouse_id")
    op.drop_column("tms_delivery_requests", "returned_to_warehouse")
    op.drop_column("tms_trip_cost_allocations", "version")
    op.drop_index("ix_tms_pods_supersedes", table_name="tms_pods")
    op.drop_constraint("fk_tms_pods_supersedes", "tms_pods", type_="foreignkey")
    op.drop_column("tms_pods", "supersedes_id")

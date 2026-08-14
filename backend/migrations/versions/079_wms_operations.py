"""079_wms_operations

Revision ID: 079_wms_operations
Revises: 078_subscription_renewal
Create Date: 2026-08-14

WMS operations: pick lists, packing slips, replenishment rules, landed costs, batch trace events.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "079_wms_operations"
down_revision: str | None = "078_subscription_renewal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pick_lists",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("order_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("warehouse_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("pick_number", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("assigned_to", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pick_lists_company_id", "pick_lists", ["company_id"])
    op.create_index("ix_pick_lists_order_id", "pick_lists", ["order_id"])
    op.create_index("ix_pick_lists_warehouse_id", "pick_lists", ["warehouse_id"])
    op.create_index("ix_pick_lists_pick_number", "pick_lists", ["pick_number"])

    op.create_table(
        "pick_list_items",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pick_list_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("pick_lists.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("batch_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("product_batches.id"), nullable=True),
        sa.Column("zone_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouse_zones.id"), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("picked_quantity", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.create_index("ix_pick_list_items_pick_list_id", "pick_list_items", ["pick_list_id"])
    op.create_index("ix_pick_list_items_product_id", "pick_list_items", ["product_id"])
    op.create_index("ix_pick_list_items_batch_id", "pick_list_items", ["batch_id"])

    op.create_table(
        "packing_slips",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("pick_list_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("pick_lists.id"), nullable=False),
        sa.Column("pack_number", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("weight", sa.Numeric(12, 3), nullable=True),
        sa.Column("packages", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_packing_slips_company_id", "packing_slips", ["company_id"])
    op.create_index("ix_packing_slips_pick_list_id", "packing_slips", ["pick_list_id"])
    op.create_index("ix_packing_slips_pack_number", "packing_slips", ["pack_number"])

    op.create_table(
        "replenishment_rules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("warehouse_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("min_quantity", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("max_quantity", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("reorder_quantity", sa.Numeric(18, 3), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("warehouse_id", "product_id", name="uq_replenish_warehouse_product"),
    )
    op.create_index("ix_replenishment_rules_company_id", "replenishment_rules", ["company_id"])
    op.create_index("ix_replenishment_rules_warehouse_id", "replenishment_rules", ["warehouse_id"])
    op.create_index("ix_replenishment_rules_product_id", "replenishment_rules", ["product_id"])

    op.create_table(
        "landed_costs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("purchase_order_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id"), nullable=True),
        sa.Column("supplier_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GEL"),
        sa.Column("allocated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_landed_costs_company_id", "landed_costs", ["company_id"])
    op.create_index("ix_landed_costs_purchase_order_id", "landed_costs", ["purchase_order_id"])
    op.create_index("ix_landed_costs_supplier_id", "landed_costs", ["supplier_id"])

    op.create_table(
        "landed_cost_allocations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("landed_cost_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("landed_costs.id"), nullable=False),
        sa.Column("batch_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("product_batches.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
    )
    op.create_index("ix_landed_cost_allocations_landed_cost_id", "landed_cost_allocations", ["landed_cost_id"])
    op.create_index("ix_landed_cost_allocations_batch_id", "landed_cost_allocations", ["batch_id"])

    op.create_table(
        "batch_trace_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("batch_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("product_batches.id"), nullable=True),
        sa.Column("serial_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("product_serials.id"), nullable=True),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=True),
        sa.Column("from_warehouse_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("to_warehouse_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_batch_trace_events_company_id", "batch_trace_events", ["company_id"])
    op.create_index("ix_batch_trace_events_batch_id", "batch_trace_events", ["batch_id"])
    op.create_index("ix_batch_trace_events_serial_id", "batch_trace_events", ["serial_id"])
    op.create_index("ix_batch_trace_events_product_id", "batch_trace_events", ["product_id"])
    op.create_index("ix_batch_trace_events_event_type", "batch_trace_events", ["event_type"])
    op.create_index("ix_batch_trace_events_created_at", "batch_trace_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("batch_trace_events")
    op.drop_table("landed_cost_allocations")
    op.drop_table("landed_costs")
    op.drop_table("replenishment_rules")
    op.drop_table("packing_slips")
    op.drop_table("pick_list_items")
    op.drop_table("pick_lists")

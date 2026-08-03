"""Enhance warehouse: zones, reserved/available, inventory counts, movements.

Revision ID: 045_warehouse_enhance
Revises: 044_hr_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "045_warehouse_enhance"
down_revision: Union[str, None] = "044_hr_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # InventoryBalance: reserved_quantity (segregation)
    op.add_column("inventory_balances", sa.Column("reserved_quantity", sa.Numeric(18, 3), server_default=sa.text("0"), nullable=False))

    # WarehouseZone table
    op.create_table(
        "warehouse_zones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("zone_type", sa.String(30), server_default="bin", nullable=False),
        sa.Column("is_pickable", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["warehouse_zones.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("warehouse_id", "code", name="uq_zone_warehouse_code"),
    )

    # ZoneBalance table
    op.create_table(
        "zone_balances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("zone_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("product_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(18, 3), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["zone_id"], ["warehouse_zones.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("zone_id", "product_id", name="uq_zone_balance_zone_product"),
    )

    # InventoryMovement enhancements (destination_warehouse_id, reference already exist)
    op.add_column("inventory_movements", sa.Column("zone_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_inv_mov_zone", "inventory_movements", "warehouse_zones", ["zone_id"], ["id"])
    op.add_column("inventory_movements", sa.Column("balance_before", sa.Numeric(18, 3), nullable=True))
    op.add_column("inventory_movements", sa.Column("reserved_before", sa.Numeric(18, 3), nullable=True))
    op.add_column("inventory_movements", sa.Column("reserved_after", sa.Numeric(18, 3), nullable=True))
    op.add_column("inventory_movements", sa.Column("reason_category", sa.String(50), nullable=True))
    op.add_column("inventory_movements", sa.Column("reference_type", sa.String(30), nullable=True))

    # InventoryCount + InventoryCountLine tables
    op.create_table(
        "inventory_counts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("zone_id", sa.Uuid(), nullable=True),
        sa.Column("count_number", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("count_type", sa.String(30), server_default="full", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("counted_by", sa.Uuid(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("counted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.ForeignKeyConstraint(["zone_id"], ["warehouse_zones.id"]),
        sa.ForeignKeyConstraint(["counted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "inventory_count_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("count_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("product_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("zone_id", sa.Uuid(), nullable=True),
        sa.Column("expected_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("counted_quantity", sa.Numeric(18, 3), nullable=True),
        sa.Column("difference", sa.Numeric(18, 3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["count_id"], ["inventory_counts.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["zone_id"], ["warehouse_zones.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("inventory_count_lines")
    op.drop_table("inventory_counts")
    op.drop_column("inventory_movements", "reference_type")
    op.drop_column("inventory_movements", "reason_category")
    op.drop_column("inventory_movements", "reserved_after")
    op.drop_column("inventory_movements", "reserved_before")
    op.drop_column("inventory_movements", "balance_before")
    op.drop_constraint("fk_inv_mov_zone", "inventory_movements", type_="foreignkey")
    op.drop_column("inventory_movements", "zone_id")
    op.drop_table("zone_balances")
    op.drop_table("warehouse_zones")
    op.drop_column("inventory_balances", "reserved_quantity")

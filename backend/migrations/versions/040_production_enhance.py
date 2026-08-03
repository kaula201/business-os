"""Enhance production: work centers, reservations, finished goods receipt, BOM cost.

Revision ID: 040_production_enhance
Revises: 039_supplier_finance_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "040_production_enhance"
down_revision: Union[str, None] = "039_supplier_finance_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # BOM enhancements
    op.add_column("bill_of_materials", sa.Column("labor_cost", sa.Numeric(14, 2), server_default=sa.text("0"), nullable=False))
    op.add_column("bill_of_materials", sa.Column("overhead_cost", sa.Numeric(14, 2), server_default=sa.text("0"), nullable=False))

    # BOM items — scrap_percent already exists in 025_production
    # WorkCenter — already created in 025_production

    # WorkOrder enhancements
    op.add_column("work_orders", sa.Column("work_center_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_wo_work_center", "work_orders", "work_centers", ["work_center_id"], ["id"])
    op.add_column("work_orders", sa.Column("scrapped_quantity", sa.Numeric(14, 3), server_default=sa.text("0"), nullable=False))
    op.add_column("work_orders", sa.Column("yield_percent", sa.Numeric(5, 2), server_default=sa.text("100"), nullable=False))
    op.add_column("work_orders", sa.Column("assigned_to", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_wo_assigned", "work_orders", "users", ["assigned_to"], ["id"])

    # ProductionReservation table
    op.create_table(
        "production_reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("work_order_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_reserved", sa.Numeric(18, 3), server_default=sa.text("0"), nullable=False),
        sa.Column("quantity_consumed", sa.Numeric(18, 3), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(20), server_default="reserved", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"],),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"],),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"],),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"],),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_order_id", "product_id", "warehouse_id", name="uq_prod_reservation_wo_product_wh"),
    )
    op.create_index("ix_prod_reservation_company", "production_reservations", ["company_id"])

    # FinishedGoodsReceipt table
    op.create_table(
        "finished_goods_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("work_order_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("receipt_number", sa.String(50), nullable=False, index=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"],),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"],),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"],),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"],),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fg_receipt_company", "finished_goods_receipts", ["company_id"])


def downgrade() -> None:
    op.drop_table("finished_goods_receipts")
    op.drop_table("production_reservations")
    op.drop_constraint("fk_wo_assigned", "work_orders", type_="foreignkey")
    op.drop_column("work_orders", "assigned_to")
    op.drop_column("work_orders", "yield_percent")
    op.drop_column("work_orders", "scrapped_quantity")
    op.drop_constraint("fk_wo_work_center", "work_orders", type_="foreignkey")
    op.drop_column("work_orders", "work_center_id")
    op.drop_column("bill_of_materials", "overhead_cost")
    op.drop_column("bill_of_materials", "labor_cost")

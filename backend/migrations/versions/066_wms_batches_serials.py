"""WMS: batch/lot and serial-number tracking.

Revision ID: 066_wms_batches_serials
Revises: 065_mv_owner_app_role
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "066_wms_batches_serials"
down_revision: Union[str, None] = "065_mv_owner_app_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("batch_number", sa.String(100), nullable=False),
        sa.Column("production_date", sa.DateTime(), nullable=True),
        sa.Column("expiry_date", sa.DateTime(), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "batch_number", name="uq_batch_company_number"),
    )
    op.create_index("ix_product_batches_company_id", "product_batches", ["company_id"])
    op.create_index("ix_product_batches_product_id", "product_batches", ["product_id"])
    op.create_index("ix_product_batches_expiry_date", "product_batches", ["expiry_date"])

    op.create_table(
        "product_serials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_batches.id"), nullable=True),
        sa.Column("serial_number", sa.String(150), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_stock"),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("sold_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "serial_number", name="uq_serial_company_number"),
    )
    op.create_index("ix_product_serials_company_id", "product_serials", ["company_id"])
    op.create_index("ix_product_serials_product_id", "product_serials", ["product_id"])
    op.create_index("ix_product_serials_status", "product_serials", ["status"])


def downgrade() -> None:
    op.drop_table("product_serials")
    op.drop_table("product_batches")

"""Create Production / Manufacturing tables: bill_of_materials, bom_items, work_orders.

Revision ID: 025_production
Revises: 024_document_management
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025_production"
down_revision: Union[str, None] = "024_document_management"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bill_of_materials",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("product_id", sa.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "code", name="uq_bom_company_code"),
    )
    op.create_table(
        "bom_items",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bom_id", sa.UUID(as_uuid=True), sa.ForeignKey("bill_of_materials.id"), nullable=False, index=True),
        sa.Column("product_id", sa.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), server_default="1", nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("bom_id", "product_id", name="uq_bom_item_product"),
    )
    op.create_table(
        "work_orders",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("bom_id", sa.UUID(as_uuid=True), sa.ForeignKey("bill_of_materials.id"), nullable=False),
        sa.Column("order_number", sa.String(50), nullable=False, index=True),
        sa.Column("product_id", sa.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("planned_quantity", sa.Numeric(14, 3), server_default="1", nullable=False),
        sa.Column("completed_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False, index=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("assigned_to", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("work_orders")
    op.drop_table("bom_items")
    op.drop_table("bill_of_materials")

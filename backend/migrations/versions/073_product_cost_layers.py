"""073_product_cost_layers

Revision ID: 073_product_cost_layers
Revises: 072_bank_reconciliation_rules
Create Date: 2026-08-09

Weighted-average cost layers for inventory valuation.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "073_product_cost_layers"
down_revision: str | None = "072_bank_reconciliation_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_cost_layers",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity_remaining", sa.Numeric(18, 3), nullable=False),
        sa.Column("weighted_avg_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("last_movement_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "product_id", name="uq_product_cost_layer_company_product"),
    )
    op.create_index("ix_product_cost_layers_company_id", "product_cost_layers", ["company_id"])
    op.create_index("ix_product_cost_layers_product_id", "product_cost_layers", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_product_cost_layers_product_id", table_name="product_cost_layers")
    op.drop_index("ix_product_cost_layers_company_id", table_name="product_cost_layers")
    op.drop_table("product_cost_layers")

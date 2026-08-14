"""080_procurement

Revision ID: 080_procurement
Revises: 079_wms_operations
Create Date: 2026-08-14

Procurement: RFQ, vendor pricelists, blanket orders, supplier scorecards.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "080_procurement"
down_revision: str | None = "079_wms_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rfqs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("rfq_number", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("required_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("awarded_supplier_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_rfqs_company_id", "rfqs", ["company_id"])
    op.create_index("ix_rfqs_rfq_number", "rfqs", ["rfq_number"])

    op.create_table(
        "rfq_lines",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rfq_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("rfqs.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("expected_price", sa.Numeric(18, 4), nullable=True),
    )
    op.create_index("ix_rfq_lines_rfq_id", "rfq_lines", ["rfq_id"])
    op.create_index("ix_rfq_lines_product_id", "rfq_lines", ["product_id"])

    op.create_table(
        "rfq_responses",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rfq_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("rfqs.id"), nullable=False),
        sa.Column("supplier_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_rfq_responses_rfq_id", "rfq_responses", ["rfq_id"])
    op.create_index("ix_rfq_responses_supplier_id", "rfq_responses", ["supplier_id"])

    op.create_table(
        "rfq_response_lines",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("response_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("rfq_responses.id"), nullable=False),
        sa.Column("rfq_line_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("rfq_lines.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GEL"),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
    )
    op.create_index("ix_rfq_response_lines_response_id", "rfq_response_lines", ["response_id"])
    op.create_index("ix_rfq_response_lines_rfq_line_id", "rfq_response_lines", ["rfq_line_id"])
    op.create_index("ix_rfq_response_lines_product_id", "rfq_response_lines", ["product_id"])

    op.create_table(
        "supplier_price_lists",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("supplier_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GEL"),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("supplier_id", "product_id", name="uq_supplier_price_supplier_product"),
    )
    op.create_index("ix_supplier_price_lists_company_id", "supplier_price_lists", ["company_id"])
    op.create_index("ix_supplier_price_lists_supplier_id", "supplier_price_lists", ["supplier_id"])
    op.create_index("ix_supplier_price_lists_product_id", "supplier_price_lists", ["product_id"])

    op.create_table(
        "blanket_orders",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("supplier_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("blanket_number", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_blanket_orders_company_id", "blanket_orders", ["company_id"])
    op.create_index("ix_blanket_orders_supplier_id", "blanket_orders", ["supplier_id"])
    op.create_index("ix_blanket_orders_blanket_number", "blanket_orders", ["blanket_number"])

    op.create_table(
        "blanket_order_lines",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("blanket_order_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("blanket_orders.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("used_quantity", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GEL"),
    )
    op.create_index("ix_blanket_order_lines_blanket_order_id", "blanket_order_lines", ["blanket_order_id"])
    op.create_index("ix_blanket_order_lines_product_id", "blanket_order_lines", ["product_id"])

    op.create_table(
        "supplier_scorecards",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("supplier_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("on_time_delivery_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("quality_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("price_index", sa.Numeric(5, 2), nullable=True),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("orders_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("on_time_orders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("supplier_id", "period", name="uq_scorecard_supplier_period"),
    )
    op.create_index("ix_supplier_scorecards_company_id", "supplier_scorecards", ["company_id"])
    op.create_index("ix_supplier_scorecards_supplier_id", "supplier_scorecards", ["supplier_id"])


def downgrade() -> None:
    op.drop_table("supplier_scorecards")
    op.drop_table("blanket_order_lines")
    op.drop_table("blanket_orders")
    op.drop_table("supplier_price_lists")
    op.drop_table("rfq_response_lines")
    op.drop_table("rfq_responses")
    op.drop_table("rfq_lines")
    op.drop_table("rfqs")

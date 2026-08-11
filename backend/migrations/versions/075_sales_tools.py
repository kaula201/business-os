"""075_sales_tools

Revision ID: 075_sales_tools
Revises: 074_company_group
Create Date: 2026-08-11

Quotations, price lists, payment terms.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "075_sales_tools"
down_revision: str | None = "074_company_group"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Payment terms
    op.create_table(
        "payment_terms",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "name", name="uq_payment_term_company_name"),
    )
    op.create_index("ix_payment_terms_company_id", "payment_terms", ["company_id"])

    # Price lists
    op.create_table(
        "price_lists",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GEL"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "name", name="uq_price_list_company_name"),
    )
    op.create_index("ix_price_lists_company_id", "price_lists", ["company_id"])

    op.create_table(
        "price_list_items",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("price_list_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("price_lists.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("min_quantity", sa.Numeric(18, 3), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("price_list_id", "product_id", "min_quantity", name="uq_price_list_item_product_qty"),
    )
    op.create_index("ix_price_list_items_price_list_id", "price_list_items", ["price_list_id"])
    op.create_index("ix_price_list_items_product_id", "price_list_items", ["product_id"])

    # Quotations
    op.create_table(
        "quotations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("client_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("quotation_number", sa.String(50), nullable=False),
        sa.Column("quotation_date", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GEL"),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("discount_percent", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("order_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "quotation_number", name="uq_quotation_company_number"),
    )
    op.create_index("ix_quotations_company_id", "quotations", ["company_id"])
    op.create_index("ix_quotations_client_id", "quotations", ["client_id"])
    op.create_index("ix_quotations_quotation_date", "quotations", ["quotation_date"])
    op.create_index("ix_quotations_status", "quotations", ["status"])

    op.create_table(
        "quotation_items",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("quotation_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("quotations.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("quotation_id", "line_number", name="uq_quotation_item_line"),
    )
    op.create_index("ix_quotation_items_quotation_id", "quotation_items", ["quotation_id"])


def downgrade() -> None:
    op.drop_index("ix_quotation_items_quotation_id", table_name="quotation_items")
    op.drop_table("quotation_items")
    op.drop_index("ix_quotations_status", table_name="quotations")
    op.drop_index("ix_quotations_quotation_date", table_name="quotations")
    op.drop_index("ix_quotations_client_id", table_name="quotations")
    op.drop_index("ix_quotations_company_id", table_name="quotations")
    op.drop_table("quotations")
    op.drop_index("ix_price_list_items_product_id", table_name="price_list_items")
    op.drop_index("ix_price_list_items_price_list_id", table_name="price_list_items")
    op.drop_table("price_list_items")
    op.drop_index("ix_price_lists_company_id", table_name="price_lists")
    op.drop_table("price_lists")
    op.drop_index("ix_payment_terms_company_id", table_name="payment_terms")
    op.drop_table("payment_terms")

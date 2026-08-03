"""Add immutable customer invoice snapshots.

Revision ID: 004_customer_invoicing
Revises: 003_bank_reconciliation
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_customer_invoicing"
down_revision: Union[str, None] = "003_bank_reconciliation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("invoices", sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("invoices", sa.Column("idempotency_key", sa.String(100), nullable=True))
    op.add_column("invoices", sa.Column("status", sa.String(20), nullable=True, server_default="issued"))
    op.add_column("invoices", sa.Column("invoice_date", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("due_date", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("currency", sa.String(3), nullable=True, server_default="GEL"))
    op.add_column("invoices", sa.Column("subtotal", sa.Numeric(18, 2), nullable=True))
    op.add_column("invoices", sa.Column("vat_amount", sa.Numeric(18, 2), nullable=True))
    op.add_column("invoices", sa.Column("order_number", sa.String(50), nullable=True))
    op.add_column("invoices", sa.Column("seller_name", sa.String(255), nullable=True))
    op.add_column("invoices", sa.Column("seller_identification_code", sa.String(50), nullable=True))
    op.add_column("invoices", sa.Column("seller_address", sa.Text(), nullable=True, server_default=""))
    op.add_column("invoices", sa.Column("seller_phone", sa.String(50), nullable=True, server_default=""))
    op.add_column("invoices", sa.Column("seller_email", sa.String(255), nullable=True, server_default=""))
    op.add_column("invoices", sa.Column("client_name", sa.String(255), nullable=True))
    op.add_column("invoices", sa.Column("client_identification_code", sa.String(50), nullable=True))
    op.add_column("invoices", sa.Column("client_address", sa.Text(), nullable=True, server_default=""))
    op.add_column("invoices", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("invoices", sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("invoices", sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()))

    op.create_foreign_key("fk_invoices_company_id", "invoices", "companies", ["company_id"], ["id"])
    op.create_foreign_key("fk_invoices_client_id", "invoices", "clients", ["client_id"], ["id"])
    op.create_foreign_key("fk_invoices_created_by", "invoices", "users", ["created_by"], ["id"])

    op.execute("""
        UPDATE invoices AS invoice
        SET company_id = orders.company_id,
            client_id = orders.client_id,
            idempotency_key = 'legacy-invoice:' || invoice.id::text,
            status = 'issued',
            invoice_date = COALESCE(invoice.created_at::date, CURRENT_DATE),
            due_date = COALESCE(invoice.created_at::date, CURRENT_DATE) + 14,
            currency = COALESCE(companies.currency, 'GEL'),
            subtotal = ROUND(orders.subtotal::numeric, 2),
            vat_amount = ROUND(orders.vat_amount::numeric, 2),
            total = ROUND(invoice.total::numeric, 2),
            order_number = orders.order_number,
            seller_name = companies.name,
            seller_identification_code = companies.identification_code,
            seller_address = COALESCE(companies.address, ''),
            seller_phone = COALESCE(companies.phone, ''),
            seller_email = COALESCE(companies.email, ''),
            client_name = clients.name,
            client_identification_code = clients.identification_code,
            client_address = COALESCE(clients.address, ''),
            updated_at = COALESCE(invoice.created_at, NOW())
        FROM orders
        JOIN companies ON companies.id = orders.company_id
        JOIN clients ON clients.id = orders.client_id
        WHERE orders.id = invoice.order_id
    """)

    op.alter_column("invoices", "total", type_=sa.Numeric(18, 2), postgresql_using="ROUND(total::numeric, 2)", nullable=False)
    for column in (
        "company_id", "client_id", "idempotency_key", "status", "invoice_date", "due_date",
        "currency", "subtotal", "vat_amount", "order_number", "seller_name",
        "seller_identification_code", "seller_address", "seller_phone", "seller_email",
        "client_name", "client_identification_code", "client_address", "updated_at",
    ):
        op.alter_column("invoices", column, nullable=False)

    op.create_index("ix_invoices_company_id", "invoices", ["company_id"])
    op.create_index("ix_invoices_client_id", "invoices", ["client_id"])
    op.create_index("ix_invoices_order_id", "invoices", ["order_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_invoice_date", "invoices", ["invoice_date"])
    op.create_index("ix_invoices_due_date", "invoices", ["due_date"])
    op.create_unique_constraint("uq_invoice_company_number", "invoices", ["company_id", "invoice_number"])
    op.create_unique_constraint("uq_invoice_company_idempotency", "invoices", ["company_id", "idempotency_key"])
    op.create_unique_constraint("uq_invoice_company_order", "invoices", ["company_id", "order_id"])

    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("line_subtotal", sa.Numeric(18, 2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_id", "line_number", name="uq_invoice_item_line"),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])

    op.execute("""
        INSERT INTO invoice_items (
            id, invoice_id, order_item_id, product_id, line_number, product_name,
            quantity, unit_price, discount_percent, line_subtotal, vat_rate, vat_amount,
            line_total, created_at
        )
        SELECT gen_random_uuid(), invoice.id, item.id, item.product_id,
               ROW_NUMBER() OVER (PARTITION BY invoice.id ORDER BY item.id),
               item.product_name,
               ROUND(item.quantity::numeric, 3),
               ROUND(item.unit_price::numeric, 2),
               ROUND(item.discount_percent::numeric, 4),
               ROUND(item.total::numeric, 2),
               CASE WHEN orders.vat_amount > 0 THEN 18 ELSE 0 END,
               CASE WHEN orders.subtotal > 0
                    THEN ROUND((item.total::numeric / orders.subtotal::numeric) * orders.vat_amount::numeric, 2)
                    ELSE 0 END,
               ROUND(item.total::numeric + CASE WHEN orders.subtotal > 0
                    THEN (item.total::numeric / orders.subtotal::numeric) * orders.vat_amount::numeric
                    ELSE 0 END, 2),
               COALESCE(invoice.created_at, NOW())
        FROM invoices AS invoice
        JOIN orders ON orders.id = invoice.order_id
        JOIN order_items AS item ON item.order_id = orders.id
    """)


def downgrade() -> None:
    # Intentionally data-preserving; historical invoices are financial records.
    pass

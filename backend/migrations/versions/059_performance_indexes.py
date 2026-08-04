"""Performance indexes for 100K+ record scaling + pg_trgm search.

Revision ID: 059_performance_indexes
Revises: 058_live_chat
Create Date: 2026-08-04

Adds tenant-scoped composite indexes on high-volume tables (clients,
products, orders, stock movements, line items) and pg_trgm GIN indexes
for substring search on names/numbers. Indexes are created with IF NOT
EXISTS semantics (safe on any existing schema).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "059_performance_indexes"
down_revision: Union[str, None] = "058_live_chat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── pg_trgm substring search (names, numbers, references) ──────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_clients_name_trgm "
        "ON clients USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_clients_identification_trgm "
        "ON clients USING gin (identification_code gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_products_name_trgm "
        "ON products USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_products_barcode_trgm "
        "ON products USING gin (barcode gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_orders_number_trgm "
        "ON orders USING gin (order_number gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_invoices_number_trgm "
        "ON invoices USING gin (invoice_number gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bank_transactions_ref_trgm "
        "ON bank_transactions USING gin (reference gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_suppliers_name_trgm "
        "ON suppliers USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_crm_leads_company_trgm "
        "ON crm_leads USING gin (company_name gin_trgm_ops)"
    )

    # ── Tenant-scoped composite indexes (company_id first) ──────────────────
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_clients_company_status "
        "ON clients (company_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_products_company_category "
        "ON products (company_id, category_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_products_company_active "
        "ON products (company_id, is_active)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_orders_company_status "
        "ON orders (company_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_orders_company_created "
        "ON orders (company_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_order_items_order_id "
        "ON order_items (order_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_order_items_product_id "
        "ON order_items (product_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_invoice_items_invoice_id "
        "ON invoice_items (invoice_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_invoice_items_product_id "
        "ON invoice_items (product_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_movements_product_created "
        "ON stock_movements (product_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_movements_type_created "
        "ON stock_movements (movement_type, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_crm_leads_company_status "
        "ON crm_leads (company_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_crm_opportunities_company_stage "
        "ON crm_opportunities (company_id, stage)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tasks_company_status "
        "ON tasks (company_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tasks_company_due "
        "ON tasks (company_id, due_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_customer_receivables_company_status "
        "ON customer_receivables (company_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_customer_payments_company_date "
        "ON customer_payments (company_id, payment_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_journal_entries_company_date "
        "ON journal_entries (company_id, entry_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_journal_entry_lines_entry_id "
        "ON journal_entry_lines (journal_entry_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_journal_entry_lines_account_id "
        "ON journal_entry_lines (gl_account_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bank_transactions_company_status "
        "ON bank_transactions (company_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inventory_balances_company_wh "
        "ON inventory_balances (company_id, warehouse_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_suppliers_company_active "
        "ON suppliers (company_id, is_active)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_purchase_orders_company_status "
        "ON purchase_orders (company_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_gl_accounts_company_code "
        "ON gl_accounts (company_id, code)"
    )


def downgrade() -> None:
    # Drop only what we created (best-effort; pg_trgm extension stays).
    op.execute("DROP INDEX IF EXISTS ix_gl_accounts_company_code")
    op.execute("DROP INDEX IF EXISTS ix_purchase_orders_company_status")
    op.execute("DROP INDEX IF EXISTS ix_suppliers_company_active")
    op.execute("DROP INDEX IF EXISTS ix_inventory_balances_company_wh")
    op.execute("DROP INDEX IF EXISTS ix_bank_transactions_company_status")
    op.execute("DROP INDEX IF EXISTS ix_journal_entry_lines_account_id")
    op.execute("DROP INDEX IF EXISTS ix_journal_entry_lines_entry_id")
    op.execute("DROP INDEX IF EXISTS ix_journal_entries_company_date")
    op.execute("DROP INDEX IF EXISTS ix_customer_payments_company_date")
    op.execute("DROP INDEX IF EXISTS ix_customer_receivables_company_status")
    op.execute("DROP INDEX IF EXISTS ix_tasks_company_due")
    op.execute("DROP INDEX IF EXISTS ix_tasks_company_status")
    op.execute("DROP INDEX IF EXISTS ix_crm_opportunities_company_stage")
    op.execute("DROP INDEX IF EXISTS ix_crm_leads_company_status")
    op.execute("DROP INDEX IF EXISTS ix_stock_movements_type_created")
    op.execute("DROP INDEX IF EXISTS ix_stock_movements_product_created")
    op.execute("DROP INDEX IF EXISTS ix_invoice_items_product_id")
    op.execute("DROP INDEX IF EXISTS ix_invoice_items_invoice_id")
    op.execute("DROP INDEX IF EXISTS ix_order_items_product_id")
    op.execute("DROP INDEX IF EXISTS ix_order_items_order_id")
    op.execute("DROP INDEX IF EXISTS ix_orders_company_created")
    op.execute("DROP INDEX IF EXISTS ix_orders_company_status")
    op.execute("DROP INDEX IF EXISTS ix_products_company_active")
    op.execute("DROP INDEX IF EXISTS ix_products_company_category")
    op.execute("DROP INDEX IF EXISTS ix_clients_company_status")
    op.execute("DROP INDEX IF EXISTS ix_crm_leads_company_trgm")
    op.execute("DROP INDEX IF EXISTS ix_suppliers_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_bank_transactions_ref_trgm")
    op.execute("DROP INDEX IF EXISTS ix_invoices_number_trgm")
    op.execute("DROP INDEX IF EXISTS ix_orders_number_trgm")
    op.execute("DROP INDEX IF EXISTS ix_products_barcode_trgm")
    op.execute("DROP INDEX IF EXISTS ix_products_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_clients_identification_trgm")
    op.execute("DROP INDEX IF EXISTS ix_clients_name_trgm")

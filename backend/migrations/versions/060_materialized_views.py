"""Materialized views for heavy aggregation reports (100K+ record scaling).

Revision ID: 060_materialized_views
Revises: 059_performance_indexes
Create Date: 2026-08-04

Three materialized views back the most expensive dashboard/report queries:
- mv_sales_daily: daily issued-invoice totals per company (revenue charts)
- mv_receivables_aging: outstanding receivable snapshot per company (KPI cards)
- mv_stock_balances: current stock per company/warehouse/product (inventory)

All views include a company_id column so every query stays tenant-scoped.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "060_materialized_views"
down_revision: Union[str, None] = "059_performance_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Sales per day (issued invoices) ─────────────────────────────────────
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_sales_daily AS
        SELECT
            company_id,
            invoice_date::date AS day,
            COUNT(*) AS invoice_count,
            SUM(total) AS total_amount
        FROM invoices
        WHERE status = 'issued'
        GROUP BY company_id, invoice_date::date
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_sales_daily "
        "ON mv_sales_daily (company_id, day)"
    )

    # ── Receivables aging snapshot (unpaid balances per invoice) ────────────
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_receivables_aging AS
        SELECT
            company_id,
            status,
            COUNT(*) AS receivable_count,
            SUM(outstanding_amount) AS outstanding_total,
            SUM(CASE WHEN status = 'overdue' THEN outstanding_amount ELSE 0 END) AS overdue_total
        FROM customer_receivables
        GROUP BY company_id, status
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_receivables_aging "
        "ON mv_receivables_aging (company_id, status)"
    )

    # ── Current stock balances ──────────────────────────────────────────────
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_stock_balances AS
        SELECT
            ib.company_id,
            ib.warehouse_id,
            ib.product_id,
            SUM(ib.quantity) AS quantity
        FROM inventory_balances ib
        GROUP BY ib.company_id, ib.warehouse_id, ib.product_id
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_stock_balances "
        "ON mv_stock_balances (company_id, warehouse_id, product_id)"
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_stock_balances")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_receivables_aging")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_sales_daily")

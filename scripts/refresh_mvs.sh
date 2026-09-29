#!/bin/bash
# Refresh Business OS materialized views (CONCURRENTLY — non-blocking).
# Runs from the backup container's cron every 5 minutes.
# Requires unique indexes on each MV (created by migration 060).

set -euo pipefail

: "${PGPASSWORD:?set PGPASSWORD}"

psql \
  -h postgres \
  -U business_os_app \
  -d business_os \
  -v ON_ERROR_STOP=1 \
  -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sales_daily" \
  -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_receivables_aging" \
  -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_stock_balances"

echo "Materialized views refreshed: $(date +%Y-%m-%d_%H:%M:%S)"

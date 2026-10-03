#!/bin/bash
# Refresh Business OS materialized views (CONCURRENTLY — non-blocking).
# Production cron is the mvrefresh service (business_os_mvrefresh, the view owner).
# Dev compose still runs this from the backup container with PGUSER set to the
# dev app role (dev has no superuser migrate step, so the refresh role is absent).
# Requires unique indexes on each MV (created by migration 060).
# The backup role cannot refresh these views: it has SELECT only.

set -euo pipefail

: "${PGPASSWORD:?set PGPASSWORD}"

psql \
  -h postgres \
  -U "${PGUSER:-business_os_mvrefresh}" \
  -d business_os \
  -v ON_ERROR_STOP=1 \
  -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sales_daily" \
  -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_receivables_aging" \
  -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_stock_balances"

echo "Materialized views refreshed: $(date +%Y-%m-%d_%H:%M:%S)"

#!/bin/bash
# Automated daily backup script for Business OS.
# Production runs this as business_os_backup (BYPASSRLS, SELECT only).
# Do not pass --enable-row-security: that flag can write a partial dump.

set -euo pipefail

umask 077

# Production sets BACKUP_DB_PASSWORD. Dev compose sets PGPASSWORD for the app role.
if [ -n "${BACKUP_DB_PASSWORD:-}" ]; then
  export PGPASSWORD="${BACKUP_DB_PASSWORD}"
fi
: "${PGPASSWORD:?set PGPASSWORD}"

PGUSER="${PGUSER:-business_os_backup}"
PGHOST="${PGHOST:-postgres}"
PGDATABASE="${PGDATABASE:-business_os}"

BACKUP_DIR="/backups"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILENAME="business_os_${TIMESTAMP}.sql.gz"
TARGET="${BACKUP_DIR}/${FILENAME}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

pg_dump \
  -h "$PGHOST" \
  -U "$PGUSER" \
  -d "$PGDATABASE" \
  --no-owner \
  --no-acl \
  --format=custom \
  | gzip > "$TARGET"

chmod 600 "$TARGET"

# Remove backups older than RETENTION_DAYS
find "$BACKUP_DIR" -name "business_os_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete

echo "Backup saved: ${TARGET} ($(du -h "${TARGET}" | cut -f1))"
echo "Retention: ${RETENTION_DAYS} days"

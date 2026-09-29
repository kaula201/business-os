#!/bin/bash
# Automated daily backup script for Business OS.
# Production runs this as business_os_backup (BYPASSRLS, SELECT only).
# Do not pass --enable-row-security: that flag can write a partial dump.
# The dump is written to *.sql.gz.partial and renamed only after pg_dump and
# gzip both succeed. A failed run deletes that partial file.

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
PARTIAL="${TARGET}.partial"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# An abandoned *.sql.gz.partial is not a backup. Drop leftovers from a crash
# before this run creates its own.
find "$BACKUP_DIR" -type f -name 'business_os_*.sql.gz.partial' -delete

remove_partial() {
  trap - ERR
  rm -f "$PARTIAL"
}
trap remove_partial ERR

pg_dump \
  -h "$PGHOST" \
  -U "$PGUSER" \
  -d "$PGDATABASE" \
  --no-owner \
  --no-acl \
  --format=custom \
  | gzip > "$PARTIAL"

chmod 600 "$PARTIAL"
mv "$PARTIAL" "$TARGET"
trap - ERR

# Retention matches completed dumps only. Never treat *.partial as a backup.
find "$BACKUP_DIR" -type f -name 'business_os_*.sql.gz' ! -name '*.partial' -mtime "+${RETENTION_DAYS}" -delete
find "$BACKUP_DIR" -type f -name 'business_os_*.sql.gz.partial' -delete

echo "Backup saved: ${TARGET} ($(du -h "${TARGET}" | cut -f1))"
echo "Retention: ${RETENTION_DAYS} days"

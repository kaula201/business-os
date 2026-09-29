#!/bin/bash
# Automated daily backup script for Business OS
# Runs inside a Docker container, dumps PostgreSQL to a timestamped file.

set -euo pipefail

: "${PGPASSWORD:?set PGPASSWORD}"

BACKUP_DIR="/backups"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILENAME="business_os_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

pg_dump \
  -h postgres \
  -U business_os_app \
  -d business_os \
  --no-owner \
  --no-acl \
  --format=custom \
  | gzip > "${BACKUP_DIR}/${FILENAME}"

# Remove backups older than RETENTION_DAYS
find "$BACKUP_DIR" -name "business_os_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete

echo "Backup saved: ${BACKUP_DIR}/${FILENAME} ($(du -h "${BACKUP_DIR}/${FILENAME}" | cut -f1))"
echo "Retention: ${RETENTION_DAYS} days"

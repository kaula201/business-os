#!/bin/sh
# BusyBox crond does not pass the container environment into jobs.
# Write only the backup role's credentials. Never copy POSTGRES_PASSWORD
# or APP_DB_PASSWORD into this crontab.
set -eu
umask 077

: "${BACKUP_DB_PASSWORD:?set BACKUP_DB_PASSWORD}"
: "${PGUSER:?set PGUSER}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

{
  printf 'PGUSER=%s\n' "$PGUSER"
  printf 'PGPASSWORD=%s\n' "$BACKUP_DB_PASSWORD"
  printf 'BACKUP_DB_PASSWORD=%s\n' "$BACKUP_DB_PASSWORD"
  printf 'RETENTION_DAYS=%s\n' "$RETENTION_DAYS"
  printf '%s\n' '0 3 * * * /scripts/backup.sh'
} > /etc/crontabs/root
chmod 600 /etc/crontabs/root

exec crond -f -l 2

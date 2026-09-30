#!/bin/sh
# REFRESH MATERIALIZED VIEW runs as business_os_app (the owner).
# This container is separate from backup so the dump role's environment
# never receives the application password.
set -eu
umask 077

: "${PGPASSWORD:?set PGPASSWORD}"

{
  printf 'PGPASSWORD=%s\n' "$PGPASSWORD"
  printf '%s\n' '*/5 * * * * /scripts/refresh_mvs.sh'
} > /etc/crontabs/root
chmod 600 /etc/crontabs/root

exec crond -f -l 2

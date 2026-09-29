#!/bin/bash
# Restore a Business OS custom-format dump into a new database.
#
# Run as the Postgres superuser. Never restore in place over business_os.
# Verify the new database, then switch traffic.
#
# Order:
#   1. Roles only (RoleSpec + env). No Alembic, so the target stays empty.
#   2. pg_restore --exit-on-error --single-transaction. A partial load rolls back.
#   3. Full migrate. Privileges are reconciled and an older dump is upgraded.
#
# Passwords come from the environment or PGPASSFILE, never from argv.
# Do not enable xtrace. This script does not print passwords.
#
# Required environment:
#   PGUSER              superuser (default business_os)
#   PGPASSWORD          or POSTGRES_PASSWORD, or PGPASSFILE
#   APP_DB_PASSWORD
#   BACKUP_DB_PASSWORD
#   JWT_SECRET_KEY
#   CORS_ORIGINS
# Optional:
#   PGHOST (default localhost), PGPORT (default 5432)
#   MIGRATE_PGHOST / MIGRATE_PGPORT
#     Host the migrate command uses. Defaults to PGHOST/PGPORT.
#     Set these when migrate runs in another network namespace.
#   RESTORE_MIGRATE_CMD
#     Word-split command that inherits the environment and runs
#     `python -m app.core.migrate_schema`. This script appends --roles-only
#     for the first step. Do not put a password in the command.
#   BACKEND_DIR
#     Used when RESTORE_MIGRATE_CMD is unset. Defaults to <repo>/backend.
#   APP_ENV (default production)

set -euo pipefail
umask 077

on_error() {
  status=$?
  echo "Restore failed (status ${status}). The target was not switched into production." >&2
  if [ "$status" -eq 0 ]; then
    status=1
  fi
  exit "$status"
}
trap on_error ERR

usage() {
  echo "Usage: scripts/restore.sh --dump FILE --target-db NAME [--force-overwrite-nonempty]" >&2
}

DUMP=""
TARGET_DB=""
FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dump)
      DUMP="${2:-}"
      shift 2
      ;;
    --target-db)
      TARGET_DB="${2:-}"
      shift 2
      ;;
    --force-overwrite-nonempty)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument." >&2
      usage
      exit 1
      ;;
  esac
done

if [ -z "$DUMP" ] || [ -z "$TARGET_DB" ]; then
  usage
  exit 1
fi
if [ ! -f "$DUMP" ]; then
  echo "Dump file not found." >&2
  exit 1
fi
if ! [[ "$TARGET_DB" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "Invalid target database name." >&2
  exit 1
fi
case "$TARGET_DB" in
  business_os|postgres|template0|template1)
    echo "Refusing to restore into ${TARGET_DB}. Use a new database name, verify, then switch." >&2
    exit 1
    ;;
esac

if [ -z "${PGPASSWORD:-}" ] && [ -n "${POSTGRES_PASSWORD:-}" ]; then
  export PGPASSWORD="${POSTGRES_PASSWORD}"
fi
if [ -z "${PGPASSWORD:-}" ] && [ -n "${PGPASSFILE:-}" ]; then
  # Read the matching pgpass line without writing it anywhere.
  PGPASSWORD="$(
    python3 - <<'PY'
import os
import sys

path = os.environ["PGPASSFILE"]
host = os.environ.get("PGHOST", "localhost")
port = os.environ.get("PGPORT", "5432")
user = os.environ.get("PGUSER", "business_os")
wanted = {host, "*", "localhost"}
try:
    lines = open(path, encoding="utf-8").read().splitlines()
except OSError:
    sys.exit(1)
for line in lines:
    if not line or line.startswith("#"):
        continue
    parts = line.split(":")
    if len(parts) < 5:
        continue
    line_host, line_port, _database, line_user, password = parts[0], parts[1], parts[2], parts[3], ":".join(parts[4:])
    if line_host not in wanted and line_host != host:
        continue
    if line_port not in {port, "*"}:
        continue
    if line_user not in {user, "*"}:
        continue
    sys.stdout.write(password)
    sys.exit(0)
sys.exit(1)
PY
  )"
  export PGPASSWORD
fi
if [ -z "${PGPASSWORD:-}" ] && [ -z "${PGPASSFILE:-}" ]; then
  echo "Set PGPASSWORD, POSTGRES_PASSWORD, or PGPASSFILE." >&2
  exit 1
fi
if [ -z "${PGPASSWORD:-}" ]; then
  echo "PGPASSFILE did not contain a password for this host." >&2
  exit 1
fi

: "${APP_DB_PASSWORD:?set APP_DB_PASSWORD}"
: "${BACKUP_DB_PASSWORD:?set BACKUP_DB_PASSWORD}"
: "${JWT_SECRET_KEY:?set JWT_SECRET_KEY}"
: "${CORS_ORIGINS:?set CORS_ORIGINS}"

export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-business_os}"
export APP_ENV="${APP_ENV:-production}"
export MIGRATE_PGHOST="${MIGRATE_PGHOST:-$PGHOST}"
export MIGRATE_PGPORT="${MIGRATE_PGPORT:-$PGPORT}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="${BACKEND_DIR:-${ROOT}/backend}"

export MIGRATION_DATABASE_URL="$(
  TARGET_DB="$TARGET_DB" python3 - <<'PY'
import os
import sys
from urllib.parse import quote

user = quote(os.environ["PGUSER"], safe="")
password = quote(os.environ["PGPASSWORD"], safe="")
host = os.environ["MIGRATE_PGHOST"]
port = os.environ["MIGRATE_PGPORT"]
database = os.environ["TARGET_DB"]
sys.stdout.write(f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}")
PY
)"

psql_at() {
  local database="$1"
  shift
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$database" -v ON_ERROR_STOP=1 -X "$@"
}

db_exists="$(psql_at postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '${TARGET_DB}'")"
db_exists="$(echo "$db_exists" | tr -d '[:space:]')"

relation_count() {
  psql_at "$TARGET_DB" -tAc "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','S','f')"
}

if [ "$db_exists" != "1" ]; then
  psql_at postgres -c "CREATE DATABASE ${TARGET_DB}"
else
  count="$(relation_count)"
  count="$(echo "$count" | tr -d '[:space:]')"
  if [ "${count:-0}" != "0" ]; then
    if [ "$FORCE" -ne 1 ]; then
      echo "Target database ${TARGET_DB} is not empty. Refusing to restore. Pass --force-overwrite-nonempty to drop it, or choose a new database name." >&2
      exit 1
    fi
    psql_at postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${TARGET_DB}' AND pid <> pg_backend_pid()"
    psql_at postgres -c "DROP DATABASE ${TARGET_DB}"
    psql_at postgres -c "CREATE DATABASE ${TARGET_DB}"
  fi
fi

run_migrate() {
  if [ -n "${RESTORE_MIGRATE_CMD:-}" ]; then
    # Word-split is intentional. The command inherits the environment.
    # shellcheck disable=SC2086
    $RESTORE_MIGRATE_CMD "$@"
  else
    (
      cd "$BACKEND_DIR"
      python3 -m app.core.migrate_schema "$@"
    )
  fi
}

run_migrate --roles-only

if [[ "$DUMP" == *.gz ]]; then
  gunzip -c "$DUMP" | pg_restore --exit-on-error --single-transaction \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$TARGET_DB"
else
  pg_restore --exit-on-error --single-transaction \
    -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$TARGET_DB" "$DUMP"
fi

run_migrate

trap - ERR
echo "Restored into ${TARGET_DB}. Verify the database, then switch traffic. This script does not replace business_os."

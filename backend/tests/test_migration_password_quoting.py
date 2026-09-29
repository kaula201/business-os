"""Password quoting for prod migrations. No database required."""
import importlib.util
from pathlib import Path

import pytest

from alembic.config import Config

from app.core.duplicate_ddl import escape_alembic_config_value
from app.core.secret_redaction import (
    PasswordRedactFilter,
    hides_password,
    public_migration_error,
    redact_url,
)


def _load_063():
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "063_rls_app_role.py"
    spec = importlib.util.spec_from_file_location("migration_063_quote", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_dollar_quote_does_not_close_early_when_password_ends_with_tag():
    quote = _load_063()._dollar_quote
    assert quote("secret$pw") == "$pwx$secret$pw$pwx$"
    assert quote("a$pw$b") == "$pwx$a$pw$b$pwx$"


def test_dollar_quote_plain_password_uses_the_short_tag():
    quote = _load_063()._dollar_quote
    assert quote("app-secret-value") == "$pw$app-secret-value$pw$"


def test_alembic_config_roundtrips_percent_in_password():
    url = "postgresql+psycopg2://business_os:100%ok@postgres:5432/business_os"
    cfg = Config()
    cfg.set_main_option("sqlalchemy.url", escape_alembic_config_value(url))
    assert cfg.get_main_option("sqlalchemy.url") == url


def test_migration_error_redacts_password_and_drops_the_chain():
    url = "postgresql+asyncpg://business_os:s3cret-value@postgres:5432/business_os"
    original = RuntimeError(f"connect failed for {url} with password s3cret-value")
    assert hides_password(original, url)
    cleaned = public_migration_error(original, url)
    rendered = str(cleaned)
    assert "s3cret-value" not in rendered
    assert "***" in redact_url(url)
    assert "s3cret-value" not in redact_url(url)
    assert cleaned.__cause__ is None


def test_managed_roles_are_the_app_role_and_the_backup_role():
    from app.core.db_roles import (
        APP_ROLE,
        BACKUP_ROLE,
        MANAGED_ROLES,
        grant_statements,
        matview_event_statements,
    )

    assert [role.name for role in MANAGED_ROLES] == ["business_os_app", "business_os_backup"]
    assert BACKUP_ROLE.password_env == "BACKUP_DB_PASSWORD"
    assert BACKUP_ROLE.dev_password == "business_os_backup"
    assert BACKUP_ROLE.attributes == ("BYPASSRLS", "NOSUPERUSER", "NOCREATEDB", "NOCREATEROLE")
    assert BACKUP_ROLE.schema_privileges == "USAGE"
    assert BACKUP_ROLE.table_privileges == "SELECT"
    assert BACKUP_ROLE.sequence_privileges == "SELECT"
    assert BACKUP_ROLE.default_table_privileges == "SELECT"
    assert BACKUP_ROLE.default_sequence_privileges == "SELECT"
    assert BACKUP_ROLE.grant_matview_select is True
    assert BACKUP_ROLE.revoke_excess is True
    assert APP_ROLE.revoke_excess is False
    assert APP_ROLE.schema_privileges == "USAGE"
    assert "NOBYPASSRLS" in APP_ROLE.attributes

    app_sql = "\n".join(grant_statements(APP_ROLE, "business_os"))
    assert "GRANT USAGE ON SCHEMA public TO business_os_app" in app_sql
    assert "GRANT ALL ON SCHEMA public TO business_os_app" not in app_sql
    assert "TEMPORARY" not in app_sql
    assert "GRANT ALL ON ALL TABLES IN SCHEMA public TO business_os_app" in app_sql
    assert "GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO business_os_app" in app_sql
    assert "ALTER DEFAULT PRIVILEGES FOR ROLE business_os IN SCHEMA public GRANT ALL ON TABLES TO business_os_app" in app_sql

    backup_sql = "\n".join(grant_statements(BACKUP_ROLE, "business_os"))
    assert "GRANT CONNECT ON DATABASE business_os TO business_os_backup" in backup_sql
    assert "GRANT USAGE ON SCHEMA public TO business_os_backup" in backup_sql
    assert "GRANT SELECT ON ALL TABLES IN SCHEMA public TO business_os_backup" in backup_sql
    assert "GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO business_os_backup" in backup_sql
    assert "GRANT SELECT ON TABLE %I TO business_os_backup" in backup_sql
    assert (
        "ALTER DEFAULT PRIVILEGES FOR ROLE business_os IN SCHEMA public "
        "GRANT SELECT ON TABLES TO business_os_backup"
    ) in backup_sql
    assert (
        "ALTER DEFAULT PRIVILEGES FOR ROLE business_os IN SCHEMA public "
        "GRANT SELECT ON SEQUENCES TO business_os_backup"
    ) in backup_sql
    for forbidden in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "ALL"):
        assert f"GRANT {forbidden}" not in backup_sql

    events = "\n".join(matview_event_statements(MANAGED_ROLES))
    assert "GRANT SELECT ON TABLE %s TO business_os_app" in events
    assert "GRANT SELECT ON TABLE %s TO business_os_backup" in events

    migration_063 = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "063_rls_app_role.py"
    source = migration_063.read_text()
    assert "business_os_backup" not in source
    assert "BACKUP_DB_PASSWORD" not in source
    assert "BACKUP_ROLE" not in source


def test_backup_role_password_is_required_in_production(monkeypatch):
    monkeypatch.delenv("BACKUP_DB_PASSWORD", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    from app.core.db_roles import BACKUP_ROLE, role_password

    try:
        role_password(BACKUP_ROLE)
    except RuntimeError as exc:
        assert "BACKUP_DB_PASSWORD" in str(exc)
    else:
        raise AssertionError("production must refuse an empty BACKUP_DB_PASSWORD")


def test_backup_role_uses_dev_password_outside_production(monkeypatch):
    monkeypatch.delenv("BACKUP_DB_PASSWORD", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    from app.core.db_roles import BACKUP_ROLE, role_password

    assert role_password(BACKUP_ROLE) == "business_os_backup"


def test_grant_sql_for_an_unregistered_reader_spec():
    """The helper still works for a spec that is not in MANAGED_ROLES."""
    from app.core.db_roles import MANAGED_ROLES, RoleSpec, grant_statements, matview_event_statements

    extra = RoleSpec(
        name="example_reader",
        password_env="EXAMPLE_DB_PASSWORD",
        dev_password="example",
        attributes=("BYPASSRLS", "NOSUPERUSER", "NOCREATEDB", "NOCREATEROLE"),
        schema_privileges="USAGE",
        table_privileges="SELECT",
        sequence_privileges="SELECT",
        default_table_privileges="SELECT",
        default_sequence_privileges="SELECT",
        grant_matview_select=True,
    )
    assert all(role.name != extra.name for role in MANAGED_ROLES)
    sql = "\n".join(grant_statements(extra, "business_os"))
    assert "GRANT SELECT ON ALL TABLES IN SCHEMA public TO example_reader" in sql
    assert "GRANT USAGE ON SCHEMA public TO example_reader" in sql
    assert "GRANT SELECT ON TABLES TO example_reader" in sql
    events = "\n".join(matview_event_statements((extra,)))
    assert "GRANT SELECT ON TABLE %s TO example_reader" in events


def test_reconcile_resets_attributes_revokes_backup_excess_and_owns_matviews():
    from app.core.db_roles import (
        APP_ROLE,
        BACKUP_ROLE,
        MATERIALIZED_VIEWS,
        attribute_statement,
        matview_owner_statements,
        revoke_excess_statements,
    )

    app_attr = attribute_statement(APP_ROLE)
    backup_attr = attribute_statement(BACKUP_ROLE)
    assert app_attr == (
        "ALTER ROLE business_os_app WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
    )
    assert backup_attr == (
        "ALTER ROLE business_os_backup WITH LOGIN BYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE"
    )
    assert "PASSWORD" not in app_attr
    assert "PASSWORD" not in backup_attr

    assert revoke_excess_statements(APP_ROLE, "business_os_restore") == []
    revoked = "\n".join(revoke_excess_statements(BACKUP_ROLE, "business_os_restore"))
    assert "REVOKE ALL PRIVILEGES ON DATABASE business_os_restore FROM business_os_backup" in revoked
    assert "REVOKE ALL PRIVILEGES ON SCHEMA public FROM business_os_backup" in revoked
    assert "REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM business_os_backup" in revoked
    assert "REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM business_os_backup" in revoked
    assert "REVOKE ALL PRIVILEGES ON TABLE %I FROM business_os_backup" in revoked
    assert "REVOKE business_os FROM business_os_backup" in revoked
    assert "REVOKE business_os_app FROM business_os_backup" in revoked
    assert (
        "ALTER DEFAULT PRIVILEGES FOR ROLE business_os IN SCHEMA public "
        "REVOKE ALL PRIVILEGES ON TABLES FROM business_os_backup"
    ) in revoked
    assert (
        "ALTER DEFAULT PRIVILEGES FOR ROLE business_os_app IN SCHEMA public "
        "REVOKE ALL PRIVILEGES ON TABLES FROM business_os_backup"
    ) in revoked
    assert "PASSWORD" not in revoked

    owners = "\n".join(matview_owner_statements())
    assert MATERIALIZED_VIEWS == ("mv_sales_daily", "mv_receivables_aging", "mv_stock_balances")
    for view in MATERIALIZED_VIEWS:
        assert f"ALTER MATERIALIZED VIEW public.{view} OWNER TO business_os_app" in owners


def test_reconcile_revokes_public_schema_create_from_public_and_managed_roles():
    """PUBLIC must not keep schema CREATE, table DML, or database TEMP.

    After migrate, CREATE is false for business_os_backup, business_os_app,
    and PUBLIC on schema public. INSERT granted to PUBLIC is revoked.
    CONNECT stays. Function EXECUTE for PUBLIC is not revoked.
    """
    from app.core.db_roles import revoke_public_schema_create_statements

    statements = revoke_public_schema_create_statements("business_os")
    joined = "\n".join(statements)
    assert "REVOKE CREATE ON SCHEMA public FROM PUBLIC" in statements
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC" in statements
    assert "REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC" in statements
    assert "REVOKE CREATE, TEMPORARY ON DATABASE business_os FROM PUBLIC" in statements
    assert "REVOKE CREATE ON SCHEMA public FROM business_os_backup" in statements
    assert "REVOKE CREATE ON SCHEMA public FROM business_os_app" in statements
    assert (
        "ALTER DEFAULT PRIVILEGES FOR ROLE business_os IN SCHEMA public "
        "REVOKE ALL ON TABLES FROM PUBLIC"
    ) in statements
    assert (
        "ALTER DEFAULT PRIVILEGES FOR ROLE business_os_app IN SCHEMA public "
        "REVOKE ALL ON SEQUENCES FROM PUBLIC"
    ) in statements
    assert "REVOKE CREATE ON SCHEMA %I FROM PUBLIC" in joined
    assert "REVOKE CREATE ON SCHEMA %I FROM business_os_backup" in joined
    assert "REVOKE CREATE ON SCHEMA %I FROM business_os_app" in joined
    assert "defaclobjtype IN ('r', 'S')" in joined
    assert "information_schema" in joined
    assert "left(n.nspname, 3) <> 'pg_'" in joined
    assert "REVOKE CONNECT" not in joined
    assert "ON FUNCTIONS FROM PUBLIC" not in joined
    assert "GRANT TEMPORARY" not in joined
    assert "PASSWORD" not in joined

    source = (Path(__file__).resolve().parents[1] / "app" / "core" / "migrate_schema.py").read_text()
    fn = source.split("async def _ensure_managed_roles", 1)[1].split(
        "async def _ensure_tenant_rls", 1
    )[0]
    assert fn.index("if roles_only:") < fn.index("grant_statements")
    assert fn.index("grant_statements") < fn.index("revoke_public_schema_create_statements")


def test_roles_only_runs_before_alembic_and_full_migrate_reconciles_after_upgrade():
    source = (Path(__file__).resolve().parents[1] / "app" / "core" / "migrate_schema.py").read_text()
    main = source.split("def main()", 1)[1]
    assert main.index("roles_only=True") < main.index("command.upgrade")
    assert main.index("command.upgrade") < main.index("_ensure_tenant_rls")
    assert main.index("_ensure_tenant_rls") < main.index("roles_only=False")
    assert "attribute_statement" in source
    assert "revoke_excess_statements" in source
    assert "matview_owner_statements" in source


def _service_block(compose: str, name: str) -> str:
    marker = f"\n  {name}:"
    start = compose.index(marker)
    rest = compose[start + 1 :]
    next_service = rest.find("\n  ", 1)
    # Services are indented two spaces and followed by a newline key.
    # Cut at the next top-level service, which starts at column 2.
    import re

    match = re.search(r"\n  [a-z0-9_]+:\n", rest[1:])
    if match is None:
        return rest
    return rest[: match.start() + 1]


def _repo_file(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / name


@pytest.mark.skipif(
    not _repo_file("docker-compose.prod.yml").is_file()
    or not _repo_file("scripts/backup.sh").is_file()
    or not _repo_file("scripts/restore.sh").is_file(),
    reason="compose and backup scripts are not in this layout",
)
def test_prod_compose_scopes_backup_password_and_script_locks_dumps():
    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker-compose.prod.yml").read_text()
    dev = (root / "docker-compose.yml").read_text()
    script = (root / "scripts" / "backup.sh").read_text()
    example = (root / ".env.example").read_text()

    migrate = _service_block(compose, "migrate")
    backend = _service_block(compose, "backend")
    backup = _service_block(compose, "backup")

    assert "BACKUP_DB_PASSWORD: " in migrate
    assert "BACKUP_DB_PASSWORD: " in backup
    assert "BACKUP_DB_PASSWORD" not in backend
    assert "POSTGRES_PASSWORD" not in backup
    assert "APP_DB_PASSWORD" not in backup
    assert "business_os_backup" in backup
    assert "PGUSER: business_os_backup" in backup
    active_script = "\n".join(
        line for line in script.splitlines() if not line.strip().startswith("#")
    )
    assert "--enable-row-security" not in active_script
    assert "umask 077" in script
    assert "set -euo pipefail" in script
    assert "chmod 600" in script
    assert 'PARTIAL="${TARGET}.partial"' in script
    assert 'gzip > "$PARTIAL"' in active_script
    assert 'gzip > "$TARGET"' not in active_script
    assert 'mv "$PARTIAL" "$TARGET"' in active_script
    assert "trap remove_partial ERR" in active_script
    assert "business_os_*.sql.gz.partial" in script
    assert "! -name '*.partial'" in script
    assert 'PGUSER="${PGUSER:-business_os_backup}"' in script
    assert "flock 9" in active_script
    assert active_script.count("-mmin +60") >= 2
    assert ".backup.lock" in script
    assert 'chmod 600 "$LOCK_FILE"' in script
    assert active_script.index("flock 9") < active_script.index("-mmin +60")
    assert "--no-owner" not in active_script
    assert "--no-acl" not in active_script
    assert "pg_dumpall" not in active_script
    assert " -g" not in active_script
    restore = (root / "scripts" / "restore.sh").read_text()
    restore_active = "\n".join(
        line for line in restore.splitlines() if not line.strip().startswith("#")
    )
    assert "set -x" not in restore_active
    assert "pg_dumpall" not in restore_active
    assert "--single-transaction" in restore
    assert "--exit-on-error" in restore
    assert "--no-owner" in restore_active
    assert "--no-acl" not in restore_active
    assert "--roles-only" in restore
    assert "--force-overwrite-nonempty" in restore
    assert "business_os|postgres|template0|template1" in restore
    assert "PGPASSFILE" in restore
    assert "BACKUP_DB_PASSWORD=change-me-backup-db-password" in example
    assert "BACKUP_DB_PASSWORD" not in dev
    assert "PGUSER: business_os_app" in dev


def test_log_filter_masks_password_in_logged_url():
    import logging

    url = "postgresql+psycopg2://business_os:s3cret-value@postgres:5432/business_os"
    redactor = PasswordRedactFilter(url)
    record = logging.LogRecord(
        name="alembic",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="migration failed for %s",
        args=(url,),
        exc_info=None,
    )
    assert redactor.filter(record) is True
    rendered = record.getMessage()
    assert "s3cret-value" not in rendered
    assert "***" in rendered

"""Login roles reconciled by the superuser migrate step.

``MANAGED_ROLES`` is the only list to edit when a later PR adds a role.
Every superuser migrate run creates a missing role, resets attributes from
the spec, re-grants privileges, and rewrites the materialized-view event
trigger. A spec with ``revoke_excess`` (the backup role) loses anything
beyond that spec first, including grants a drifted dump restored. Grants to
``PUBLIC`` are not part of a role, so the same run revokes schema
``CREATE``, table and sequence privileges, and database ``CREATE`` and
``TEMPORARY`` from ``PUBLIC``. ``CONNECT`` and function ``EXECUTE`` stay.
``business_os_app`` keeps ``USAGE`` on the schema, not ``CREATE``. Migration
``063`` keeps creating ``business_os_app`` itself so an incremental upgrade
still works; it calls the same helpers with that one spec and does not walk
``MANAGED_ROLES``.

``BACKUP_ROLE`` (``business_os_backup``) is created only here. ``BYPASSRLS``
can be granted by a superuser, which the migrate service is. Migration
``063`` does not create this role. The spec is read-only: ``USAGE`` on the
schema, ``SELECT`` on tables, sequences, and materialized views, and the
same ``SELECT`` via ``ALTER DEFAULT PRIVILEGES`` for objects created later
by ``business_os``. Passwords of existing roles are not changed here.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from sqlalchemy import text

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ATTRIBUTES = frozenset(
    {
        "SUPERUSER",
        "NOSUPERUSER",
        "BYPASSRLS",
        "NOBYPASSRLS",
        "CREATEDB",
        "NOCREATEDB",
        "CREATEROLE",
        "NOCREATEROLE",
        "INHERIT",
        "NOINHERIT",
        "REPLICATION",
        "NOREPLICATION",
    }
)
_OBJECT_PRIVILEGES = frozenset(
    {"ALL", "SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER", "USAGE"}
)
_SCHEMA_PRIVILEGES = frozenset({"ALL", "USAGE", "CREATE"})
_DATABASE_PRIVILEGES = frozenset({"CONNECT", "CREATE", "TEMPORARY"})
# Objects created by the production superuser. Default privileges are for this
# role, which is also POSTGRES_USER in compose.
GRANTOR_ROLE = "business_os"


def _ident(value: str, label: str) -> str:
    if not _IDENT.fullmatch(value):
        raise RuntimeError(f"Invalid {label}.")
    return value


def _words(values: tuple[str, ...], allowed: frozenset[str], label: str) -> str:
    if not values or any(value not in allowed for value in values):
        raise RuntimeError(f"Invalid {label}.")
    return " ".join(values)


def _database_privileges(values: tuple[str, ...]) -> str:
    """Comma-separated database privileges. The tuple order is the GRANT order."""
    if not values or any(value not in _DATABASE_PRIVILEGES for value in values):
        raise RuntimeError("Invalid database privilege.")
    return ", ".join(values)


def _priv(value: str, allowed: frozenset[str], label: str) -> str:
    parts = value.split()
    if not parts or any(part not in allowed for part in parts):
        raise RuntimeError(f"Invalid {label}.")
    return " ".join(parts)


@dataclass(frozen=True)
class RoleSpec:
    """One login role and the privileges the migrate step must keep in place."""

    name: str
    password_env: str
    dev_password: str
    attributes: tuple[str, ...]
    schema_privileges: str
    table_privileges: str
    sequence_privileges: str
    default_table_privileges: str
    default_sequence_privileges: str
    grant_matview_select: bool = False
    # When non-empty, table privileges are granted only on these public
    # tables and no ALL TABLES / ALL SEQUENCES / ALTER DEFAULT PRIVILEGES
    # grants are emitted.
    source_tables: tuple[str, ...] = ()
    # Database privileges re-applied on every reconcile. CONNECT is required
    # to log in once PUBLIC loses extra rights. TEMPORARY is only for the
    # role that owns the materialized views: REFRESH CONCURRENTLY creates a
    # temporary table in that session.
    # The TEMPORARY grant belongs to the dedicated refresh role in #7.
    # business_os_app loses it then.
    database_privileges: tuple[str, ...] = ("CONNECT",)
    # When true, every reconcile revokes privileges outside this spec before
    # the grants are applied again. A dump is not a privilege source.
    revoke_excess: bool = False

    def __post_init__(self) -> None:
        _ident(self.name, "role")
        _words(self.attributes, _ATTRIBUTES, "attribute")
        _priv(self.schema_privileges, _SCHEMA_PRIVILEGES, "schema privilege")
        _priv(self.table_privileges, _OBJECT_PRIVILEGES, "table privilege")
        _priv(self.sequence_privileges, _OBJECT_PRIVILEGES, "sequence privilege")
        _priv(self.default_table_privileges, _OBJECT_PRIVILEGES, "default table privilege")
        _priv(self.default_sequence_privileges, _OBJECT_PRIVILEGES, "default sequence privilege")
        for table in self.source_tables:
            _ident(table, "source table")
        _database_privileges(self.database_privileges)


APP_ROLE = RoleSpec(
    name="business_os_app",
    password_env="APP_DB_PASSWORD",
    dev_password="business_os_app",
    attributes=("NOSUPERUSER", "NOBYPASSRLS", "NOCREATEDB", "NOCREATEROLE"),
    schema_privileges="USAGE",
    table_privileges="ALL",
    sequence_privileges="ALL",
    default_table_privileges="ALL",
    default_sequence_privileges="ALL",
    grant_matview_select=True,
    database_privileges=("CONNECT",),
)

# Read-only dump role. BYPASSRLS is required so pg_dump can read every tenant.
# --enable-row-security is not acceptable: it can write a partial dump.
# LOGIN is set by create_role_if_missing. No INSERT/UPDATE/DELETE/TRUNCATE.
BACKUP_ROLE = RoleSpec(
    name="business_os_backup",
    password_env="BACKUP_DB_PASSWORD",
    dev_password="business_os_backup",
    attributes=("BYPASSRLS", "NOSUPERUSER", "NOCREATEDB", "NOCREATEROLE"),
    schema_privileges="USAGE",
    table_privileges="SELECT",
    sequence_privileges="SELECT",
    default_table_privileges="SELECT",
    default_sequence_privileges="SELECT",
    grant_matview_select=True,
    revoke_excess=True,
)


# Dedicated materialized-view refresh role. Owns the three matviews and has
# SELECT only on the three source tables. BYPASSRLS lets it read every
# tenant's source rows for the cross-tenant aggregate refresh. The last three
# default-privilege fields are ignored because source_tables is set.
MVREFRESH_ROLE = RoleSpec(
    name="business_os_mvrefresh",
    password_env="MVREFRESH_DB_PASSWORD",
    dev_password="business_os_mvrefresh",
    attributes=("BYPASSRLS", "NOSUPERUSER", "NOCREATEDB", "NOCREATEROLE", "NOINHERIT"),
    schema_privileges="USAGE",
    table_privileges="SELECT",
    sequence_privileges="SELECT",
    default_table_privileges="SELECT",
    default_sequence_privileges="SELECT",
    grant_matview_select=False,
    source_tables=("invoices", "customer_receivables", "inventory_balances"),
    database_privileges=("CONNECT", "TEMPORARY"),
    revoke_excess=True,
)


# REFRESH CONCURRENTLY requires the owner. Migration 065 sets this once;
# a dump restored with --no-owner leaves the views owned by the superuser,
# and 065 does not re-run when the dump is already at head.
MATERIALIZED_VIEWS: tuple[str, ...] = (
    "mv_sales_daily",
    "mv_receivables_aging",
    "mv_stock_balances",
)


# Reconciled after ``upgrade head`` when the connection is a superuser.
# Migration 063 does not walk this tuple and does not create BACKUP_ROLE.
MANAGED_ROLES: tuple[RoleSpec, ...] = (APP_ROLE, BACKUP_ROLE, MVREFRESH_ROLE)


def dollar_quote(value: str, role_name: str) -> str:
    """Quote a password so the closer cannot collide with the value.

    ``$pw$secret$pw$pw$`` is parsed as the string ``secret`` plus leftover
    ``pw$`` when the password ends in ``$pw``. Grow the tag until the
    delimiter does not occur in the value and is not formed on the boundary
    with the closing delimiter.
    """
    tag = "pw"
    for _ in range(len(value) + 2):
        delimiter = f"${tag}$"
        if delimiter not in (value + delimiter)[:-1]:
            return f"{delimiter}{value}{delimiter}"
        tag += "x"
    raise RuntimeError(f"Could not quote a password for role {role_name}.")


def role_password(spec: RoleSpec) -> str:
    password = os.environ.get(spec.password_env, "").strip()
    if password:
        return password
    app_env = os.environ.get("APP_ENV", "").strip().lower()
    if app_env in {"production", "prod"}:
        raise RuntimeError(f"{spec.password_env} must be set when APP_ENV is production")
    return spec.dev_password


def create_role_if_missing(bind, spec: RoleSpec) -> None:
    """Create ``spec`` on a sync connection. A failure does not include the SQL.

    Existing roles keep their current password. Callers that are not a
    superuser never reach this on the migrate path; Alembic still calls it
    for ``business_os_app`` and skips the statement when the role exists.
    """
    exists = bind.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
        {"name": spec.name},
    ).scalar()
    if exists:
        return
    statement = (
        f"CREATE ROLE {spec.name} LOGIN PASSWORD {dollar_quote(role_password(spec), spec.name)} "
        f"{_words(spec.attributes, _ATTRIBUTES, 'attribute')}"
    )
    nested = bind.begin_nested()
    try:
        is_superuser = bind.execute(
            text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        ).scalar()
        if is_superuser:
            # Panic is above ERROR, so a failed statement is not written to
            # the server log. Restored before the savepoint commits.
            bind.execute(text("SELECT set_config('log_min_error_statement', 'panic', true)"))
        bind.execute(text(statement))
        if is_superuser:
            bind.execute(text("SELECT set_config('log_min_error_statement', 'error', true)"))
        nested.commit()
    except Exception:
        try:
            nested.rollback()
        except Exception:
            pass
        raise RuntimeError(f"Failed to create database role {spec.name}.") from None


def attribute_statement(spec: RoleSpec) -> str:
    """Reset login and the spec attributes. Does not change the password.

    Applied on every superuser reconcile, including when the role already
    existed. A dump cannot grant ``BYPASSRLS`` to the app role and have it
    survive the next migrate.
    """
    name = _ident(spec.name, "role")
    attributes = _words(spec.attributes, _ATTRIBUTES, "attribute")
    return f"ALTER ROLE {name} WITH LOGIN {attributes}"


def revoke_excess_statements(spec: RoleSpec, database: str) -> list[str]:
    """Strip privileges that are not on ``spec``.

    Only specs with ``revoke_excess`` are stripped. The app role is granted
    ``ALL`` again instead, so a missing grant is restored without a blanket
    revoke. Its memberships are not touched here (that stays in #6).
    Default privileges are revoked for both the superuser and the
    app role: restored objects may have been created by either.

    Role memberships are cluster-wide and are not removed by ``REVOKE ALL
    PRIVILEGES``. Every membership recorded in ``pg_auth_members`` is
    revoked, including ``pg_write_all_data`` and ``pg_read_all_data``, not
    only ``business_os`` and ``business_os_app``.
    """
    if not spec.revoke_excess:
        return []
    name = _ident(spec.name, "role")
    database = _ident(database, "database")
    grantor = _ident(GRANTOR_ROLE, "grantor")
    app = _ident(APP_ROLE.name, "role")
    return [
        f"""
        DO $$
        DECLARE
            granted text;
        BEGIN
            FOR granted IN
                SELECT r.rolname
                FROM pg_auth_members m
                JOIN pg_roles r ON r.oid = m.roleid
                JOIN pg_roles member ON member.oid = m.member
                WHERE member.rolname = '{name}'
            LOOP
                EXECUTE format('REVOKE %I FROM {name}', granted);
            END LOOP;
        END
        $$;
        """,
        f"REVOKE {grantor} FROM {name}",
        f"REVOKE {app} FROM {name}",
        f"REVOKE ALL PRIVILEGES ON DATABASE {database} FROM {name}",
        f"REVOKE ALL PRIVILEGES ON SCHEMA public FROM {name}",
        f"""
        DO $$
        DECLARE
            rel text;
        BEGIN
            FOR rel IN
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
                  AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = '{name}')
            LOOP
                EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM {name}', rel);
            END LOOP;
        END
        $$;
        """,
        f"REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {name}",
        f"REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM {name}",
        f"""
        DO $$
        DECLARE
            mv text;
        BEGIN
            FOR mv IN
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'm'
                  AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = '{name}')
            LOOP
                EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM {name}', mv);
            END LOOP;
        END
        $$;
        """,
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {grantor} IN SCHEMA public "
        f"REVOKE ALL PRIVILEGES ON TABLES FROM {name}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {grantor} IN SCHEMA public "
        f"REVOKE ALL PRIVILEGES ON SEQUENCES FROM {name}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {grantor} IN SCHEMA public "
        f"REVOKE ALL PRIVILEGES ON FUNCTIONS FROM {name}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {app} IN SCHEMA public "
        f"REVOKE ALL PRIVILEGES ON TABLES FROM {name}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {app} IN SCHEMA public "
        f"REVOKE ALL PRIVILEGES ON SEQUENCES FROM {name}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {app} IN SCHEMA public "
        f"REVOKE ALL PRIVILEGES ON FUNCTIONS FROM {name}",
    ]


def revoke_public_schema_create_statements(
    database: str,
    roles: tuple[RoleSpec, ...] | list[RoleSpec] | None = None,
) -> list[str]:
    """Drop privileges ``PUBLIC`` must not keep, and schema CREATE on managed roles.

    ``REVOKE ALL`` on ``business_os_backup`` does not touch grants to
    ``PUBLIC``. A drifted ``GRANT CREATE ON SCHEMA public TO PUBLIC``
    (``nspacl`` ``=UC``) or ``GRANT INSERT ON ... TO PUBLIC`` lets the
    backup role write or run DDL. ``REVOKE`` does nothing when the
    privilege is already absent, so this is safe on every full superuser
    reconcile. It runs after the spec grants.

    ``ALL TABLES`` in PostgreSQL 16 includes materialized views. Function
    ``EXECUTE`` for ``PUBLIC`` is left in place. ``CONNECT`` on the database
    stays with ``PUBLIC``; ``CREATE`` and ``TEMPORARY`` do not. The app role's
    own ``TEMPORARY`` comes from ``database_privileges`` and is re-granted
    every run. The backup role's spec does not include it.
    Default privileges for tables and sequences are
    cleared for ``PUBLIC`` so a new table does not inherit a public grant.
    System schemas (``pg_*``, ``information_schema``) are left alone.
    """
    database = _ident(database, "database")
    managed = MANAGED_ROLES if roles is None else roles
    names = [_ident(spec.name, "role") for spec in managed]
    grantor = _ident(GRANTOR_ROLE, "grantor")
    app = _ident(APP_ROLE.name, "role")
    statements = [
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
        "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC",
        "REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC",
        f"REVOKE CREATE, TEMPORARY ON DATABASE {database} FROM PUBLIC",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {grantor} IN SCHEMA public "
        "REVOKE ALL ON TABLES FROM PUBLIC",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {grantor} IN SCHEMA public "
        "REVOKE ALL ON SEQUENCES FROM PUBLIC",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {app} IN SCHEMA public "
        "REVOKE ALL ON TABLES FROM PUBLIC",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {app} IN SCHEMA public "
        "REVOKE ALL ON SEQUENCES FROM PUBLIC",
    ]
    statements.extend(f"REVOKE CREATE ON SCHEMA public FROM {name}" for name in names)
    role_lines = "\n".join(
        f"                EXECUTE format('REVOKE CREATE ON SCHEMA %I FROM {name}', s);"
        for name in names
    )
    statements.append(
        f"""
        DO $$
        DECLARE
            s text;
        BEGIN
            FOR s IN
                SELECT n.nspname
                FROM pg_namespace n
                WHERE n.nspname <> 'information_schema'
                  AND left(n.nspname, 3) <> 'pg_'
            LOOP
                EXECUTE format('REVOKE CREATE ON SCHEMA %I FROM PUBLIC', s);
{role_lines}
            END LOOP;
        END
        $$;
        """
    )
    # Any grantor, not only the two roles above. Skip functions so PUBLIC
    # keeps EXECUTE. A missing schema means the default applies globally.
    statements.append(
        """
        DO $$
        DECLARE
            rec record;
            kind text;
        BEGIN
            FOR rec IN
                SELECT n.nspname AS schema_name,
                       r.rolname AS grantor,
                       d.defaclobjtype
                FROM pg_default_acl d
                JOIN pg_roles r ON r.oid = d.defaclrole
                LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
                WHERE d.defaclobjtype IN ('r', 'S')
                  AND EXISTS (
                      SELECT 1
                      FROM aclexplode(d.defaclacl) AS e
                      WHERE e.grantee = 0
                  )
            LOOP
                kind := CASE rec.defaclobjtype WHEN 'r' THEN 'TABLES' ELSE 'SEQUENCES' END;
                IF rec.schema_name IS NULL THEN
                    EXECUTE format(
                        'ALTER DEFAULT PRIVILEGES FOR ROLE %I REVOKE ALL ON %s FROM PUBLIC',
                        rec.grantor,
                        kind
                    );
                ELSE
                    EXECUTE format(
                        'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I REVOKE ALL ON %s FROM PUBLIC',
                        rec.grantor,
                        rec.schema_name,
                        kind
                    );
                END IF;
            END LOOP;
        END
        $$;
        """
    )
    return statements


def matview_owner_statements(owner: str | None = None) -> list[str]:
    """Give the specified role ownership of the three refresh views, if they exist.

    The dedicated refresh role owns them; the caller passes MVREFRESH_ROLE.name.
    """
    owner_name = _ident(owner or MVREFRESH_ROLE.name, "role")
    statements: list[str] = []
    for view in MATERIALIZED_VIEWS:
        view_name = _ident(view, "materialized view")
        statements.append(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relname = '{view_name}'
                      AND c.relkind = 'm'
                ) THEN
                    EXECUTE 'ALTER MATERIALIZED VIEW public.{view_name} OWNER TO {owner_name}';
                END IF;
            END
            $$;
            """
        )
    return statements


def grant_statements(spec: RoleSpec, database: str) -> list[str]:
    """Privilege SQL for one role. ``database`` is the current database name."""
    name = _ident(spec.name, "role")
    database = _ident(database, "database")
    grantor = _ident(GRANTOR_ROLE, "grantor")
    schema = _priv(spec.schema_privileges, _SCHEMA_PRIVILEGES, "schema privilege")
    tables = _priv(spec.table_privileges, _OBJECT_PRIVILEGES, "table privilege")
    sequences = _priv(spec.sequence_privileges, _OBJECT_PRIVILEGES, "sequence privilege")
    default_tables = _priv(spec.default_table_privileges, _OBJECT_PRIVILEGES, "default table privilege")
    default_sequences = _priv(
        spec.default_sequence_privileges, _OBJECT_PRIVILEGES, "default sequence privilege"
    )
    # Drop database privileges the spec does not list, then grant the spec.
    # A dump can leave TEMPORARY on the backup role; PUBLIC's TEMPORARY is
    # removed separately and does not cover this direct grant.
    statements = [
        f"REVOKE {privilege} ON DATABASE {database} FROM {name}"
        for privilege in ("CONNECT", "CREATE", "TEMPORARY")
        if privilege not in spec.database_privileges
    ]
    statements.append(
        f"GRANT {_database_privileges(spec.database_privileges)} ON DATABASE {database} TO {name}"
    )
    statements.append(f"GRANT {schema} ON SCHEMA public TO {name}")
    if spec.source_tables:
        # Only the explicitly listed source tables. No ALL TABLES, no
        # ALL SEQUENCES, and no ALTER DEFAULT PRIVILEGES grants.
        for table in spec.source_tables:
            statements.append(
                f"""
                DO $$
                BEGIN
                    IF to_regclass('public.{table}') IS NOT NULL THEN
                        EXECUTE 'GRANT {tables} ON TABLE public.{table} TO {name}';
                    END IF;
                END
                $$;
                """
            )
    else:
        statements.extend(
            [
                f"GRANT {tables} ON ALL TABLES IN SCHEMA public TO {name}",
                f"GRANT {sequences} ON ALL SEQUENCES IN SCHEMA public TO {name}",
            ]
        )
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {grantor} IN SCHEMA public "
            f"GRANT {default_tables} ON TABLES TO {name}"
        )
        statements.append(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {grantor} IN SCHEMA public "
            f"GRANT {default_sequences} ON SEQUENCES TO {name}"
        )
    if spec.grant_matview_select:
        statements.append(
            f"""
            DO $$
            DECLARE
                mv text;
            BEGIN
                FOR mv IN
                    SELECT c.relname
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relkind = 'm'
                      AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = '{name}')
                LOOP
                    EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM {name}', mv);
                    EXECUTE format('GRANT SELECT ON TABLE %I TO {name}', mv);
                END LOOP;
            END
            $$;
            """
        )
    return statements


def matview_event_statements(roles: tuple[RoleSpec, ...] | list[RoleSpec]) -> list[str]:
    """Replace the matview event trigger so every listed role keeps SELECT.

    ``GRANT`` on tables does not cover materialized views, and
    ``ALTER DEFAULT PRIVILEGES`` does not either. One function grants each
    role that set ``grant_matview_select``.
    """
    names = [_ident(role.name, "role") for role in roles if role.grant_matview_select]
    if not names:
        return [
            "DROP EVENT TRIGGER IF EXISTS business_os_grant_matview",
            "DROP FUNCTION IF EXISTS business_os_grant_matview()",
        ]
    executes = "\n".join(
        "                EXECUTE format(\n"
        f"                    'GRANT SELECT ON TABLE %s TO {name}',\n"
        "                    obj.object_identity\n"
        "                );"
        for name in names
    )
    return [
        f"""
        CREATE OR REPLACE FUNCTION business_os_grant_matview()
        RETURNS event_trigger
        LANGUAGE plpgsql
        AS $fn$
        DECLARE
            obj record;
        BEGIN
            FOR obj IN
                SELECT object_identity
                FROM pg_event_trigger_ddl_commands()
                WHERE command_tag = 'CREATE MATERIALIZED VIEW'
            LOOP
{executes}
            END LOOP;
        END;
        $fn$;
        """,
        "DROP EVENT TRIGGER IF EXISTS business_os_grant_matview",
        """
        CREATE EVENT TRIGGER business_os_grant_matview
        ON ddl_command_end
        WHEN TAG IN ('CREATE MATERIALIZED VIEW')
        EXECUTE FUNCTION business_os_grant_matview()
        """,
    ]

"""Superuser reconcile removes drifted grants. Skips locally without the URL.

CI sets TEST_SUPERUSER_DATABASE_URL from the postgres service superuser.
A missing value fails in CI. Outside CI the drift test skips.
"""
import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

DRIFT_DATABASE = "business_os_reconcile_test"

_PRIVILEGES = text(
    """
    SELECT
        has_table_privilege('business_os_backup', 'companies', 'INSERT') AS backup_insert,
        has_table_privilege('business_os_backup', 'companies', 'SELECT') AS backup_select,
        has_schema_privilege('business_os_backup', 'public', 'CREATE') AS backup_schema_create,
        has_schema_privilege('business_os_app', 'public', 'CREATE') AS app_schema_create,
        has_schema_privilege('public', 'public', 'CREATE') AS public_schema_create,
        has_schema_privilege('business_os_app', 'public', 'USAGE') AS app_usage,
        has_database_privilege('business_os_app', current_database(), 'TEMP') AS app_temp,
        has_database_privilege('business_os_backup', current_database(), 'TEMP') AS backup_temp,
        has_database_privilege('public', current_database(), 'TEMP') AS public_temp,
        has_database_privilege('business_os_backup', current_database(), 'CREATE') AS backup_db_create,
        has_database_privilege('public', current_database(), 'CREATE') AS public_db_create,
        has_database_privilege('business_os_app', current_database(), 'CONNECT') AS app_connect,
        has_database_privilege('business_os_backup', current_database(), 'CONNECT') AS backup_connect,
        has_database_privilege('public', current_database(), 'CONNECT') AS public_connect,
        EXISTS (
            SELECT 1
            FROM pg_auth_members m
            JOIN pg_roles granted ON granted.oid = m.roleid
            JOIN pg_roles member ON member.oid = m.member
            WHERE member.rolname = 'business_os_backup'
              AND granted.rolname = 'pg_write_all_data'
        ) AS backup_write_all_data,
        EXISTS (
            SELECT 1
            FROM pg_auth_members m
            JOIN pg_roles member ON member.oid = m.member
            WHERE member.rolname = 'business_os_backup'
        ) AS backup_any_membership
    """
)

# App memberships stay with issue #6. Snapshot both directions: rows where
# business_os_app is the member, and rows where it is the granted role.
_APP_MEMBERSHIPS = text(
    """
    SELECT granted.rolname AS granted_role,
           member.rolname AS member_role,
           m.admin_option,
           m.inherit_option,
           m.set_option
    FROM pg_auth_members m
    JOIN pg_roles granted ON granted.oid = m.roleid
    JOIN pg_roles member ON member.oid = m.member
    WHERE member.rolname = 'business_os_app'
       OR granted.rolname = 'business_os_app'
    ORDER BY granted.rolname, member.rolname, m.admin_option, m.inherit_option, m.set_option
    """
)


def _superuser_url() -> str:
    url = os.environ.get("TEST_SUPERUSER_DATABASE_URL", "").strip()
    if url:
        return url
    if os.environ.get("CI"):
        pytest.fail("TEST_SUPERUSER_DATABASE_URL is required in CI")
    pytest.skip("TEST_SUPERUSER_DATABASE_URL is unset")


def test_guard_aborts_when_connected_database_is_not_the_target(monkeypatch):
    from app.core.migrate_schema import (
        UnexpectedDatabase,
        assert_expected_database,
        expected_database_name,
    )

    monkeypatch.delenv("EXPECTED_DATABASE", raising=False)
    monkeypatch.delenv("TARGET_DB", raising=False)
    assert expected_database_name() is None
    assert_expected_database("business_os", None)

    monkeypatch.setenv("TARGET_DB", "business_os_restore")
    assert expected_database_name() == "business_os_restore"
    assert_expected_database("business_os_restore", expected_database_name())
    with pytest.raises(UnexpectedDatabase, match="expected business_os_restore"):
        assert_expected_database("business_os", expected_database_name())

    monkeypatch.setenv("EXPECTED_DATABASE", "business_os_restore")
    assert expected_database_name() == "business_os_restore"
    monkeypatch.setenv("TARGET_DB", "business_os")
    with pytest.raises(UnexpectedDatabase, match="different databases"):
        expected_database_name()


def _assert_clean(row) -> None:
    assert row.backup_insert is False
    assert row.backup_select is True
    assert row.backup_schema_create is False
    assert row.app_schema_create is False
    assert row.public_schema_create is False
    assert row.app_usage is True
    assert row.app_temp is True
    assert row.backup_temp is False
    assert row.public_temp is False
    assert row.backup_db_create is False
    assert row.public_db_create is False
    assert row.app_connect is True
    assert row.backup_connect is True
    assert row.public_connect is True
    assert row.backup_write_all_data is False
    assert row.backup_any_membership is False


def _membership_rows(result) -> tuple:
    return tuple(
        (row.granted_role, row.member_role, row.admin_option, row.inherit_option, row.set_option)
        for row in result
    )


async def _inject(conn) -> None:
    await conn.execute(text("GRANT INSERT ON TABLE public.companies TO business_os_backup"))
    await conn.execute(text("GRANT CREATE ON SCHEMA public TO PUBLIC"))
    await conn.execute(text("GRANT CREATE ON SCHEMA public TO business_os_backup"))
    await conn.execute(
        text(
            """
            DO $$
            BEGIN
                EXECUTE format(
                    'GRANT CREATE ON DATABASE %I TO PUBLIC',
                    current_database()
                );
                EXECUTE format(
                    'GRANT CREATE ON DATABASE %I TO business_os_backup',
                    current_database()
                );
                EXECUTE format(
                    'GRANT TEMPORARY ON DATABASE %I TO PUBLIC',
                    current_database()
                );
                EXECUTE format(
                    'GRANT TEMPORARY ON DATABASE %I TO business_os_backup',
                    current_database()
                );
            END
            $$;
            """
        )
    )
    await conn.execute(text("GRANT pg_write_all_data TO business_os_backup"))


async def test_superuser_reconcile_removes_injected_drift():
    """Real _ensure_managed_roles, twice, on a database the CI superuser owns."""
    from app.core.migrate_schema import _ensure_managed_roles

    if not DRIFT_DATABASE.endswith("_test"):
        raise RuntimeError("drift database name must end with _test")
    url = make_url(_superuser_url())
    maintenance = url.set(database="postgres")
    admin = create_async_engine(maintenance, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    drift = create_async_engine(
        url.set(database=DRIFT_DATABASE),
        poolclass=NullPool,
    )
    try:
        async with admin.connect() as conn:
            is_super = bool(
                await conn.scalar(
                    text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
                )
            )
            if not is_super:
                pytest.fail("TEST_SUPERUSER_DATABASE_URL is not a superuser")
            await conn.execute(
                text(f"DROP DATABASE IF EXISTS {DRIFT_DATABASE} WITH (FORCE)")
            )
            await conn.execute(text(f"CREATE DATABASE {DRIFT_DATABASE}"))

        async with drift.begin() as conn:
            await conn.execute(
                text(
                    """
                    CREATE TABLE companies (
                        id uuid PRIMARY KEY,
                        company_id uuid NOT NULL
                    )
                    """
                )
            )
        await _ensure_managed_roles(drift, roles_only=False)

        for _ in range(2):
            async with drift.begin() as conn:
                await _inject(conn)
            async with drift.connect() as conn:
                dirty = (await conn.execute(_PRIVILEGES)).one()
            assert dirty.backup_insert is True
            assert dirty.public_schema_create is True
            assert dirty.app_schema_create is True
            assert dirty.backup_schema_create is True
            assert dirty.backup_temp is True
            assert dirty.public_temp is True
            assert dirty.backup_db_create is True
            assert dirty.public_db_create is True
            assert dirty.backup_write_all_data is True
            async with drift.connect() as conn:
                app_memberships = _membership_rows((await conn.execute(_APP_MEMBERSHIPS)).all())
            await _ensure_managed_roles(drift, roles_only=False)
            async with drift.connect() as conn:
                _assert_clean((await conn.execute(_PRIVILEGES)).one())
                assert _membership_rows((await conn.execute(_APP_MEMBERSHIPS)).all()) == app_memberships
    finally:
        await drift.dispose()
        async with admin.connect() as conn:
            await conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'business_os_backup') THEN
                            EXECUTE 'REVOKE pg_write_all_data FROM business_os_backup';
                        END IF;
                    END
                    $$;
                    """
                )
            )
            await conn.execute(
                text(f"DROP DATABASE IF EXISTS {DRIFT_DATABASE} WITH (FORCE)")
            )
        await admin.dispose()

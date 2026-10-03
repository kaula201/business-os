"""Tenant-scope helpers: fail-closed RLS policy and transaction-local settings."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text

from app.core.database import current_company_id
from app.core.db_roles import MATERIALIZED_VIEWS

logger = logging.getLogger(__name__)

TENANT_POLICY_PREDICATE = (
    "company_id::text = NULLIF(current_setting('app.current_company_id', true), '') "
    "OR current_setting('app.rls_bypass', true) = 'on'"
)


def tenant_rls_sql() -> str:
    """Return a DO block that ENABLEs+FORCEs RLS, drops other PERMISSIVE policies, and recreates tenant_isolation.

    The policy is applied to every public base table (relkind 'r') that has a
    non-dropped company_id column. It uses the fail-closed predicate from
    TENANT_POLICY_PREDICATE for both USING and WITH CHECK.
    """
    predicate_sql = TENANT_POLICY_PREDICATE.replace("'", "''")
    return f"""
DO $$
DECLARE
    t text;
    p text;
BEGIN
    FOR t IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND a.attname = 'company_id'
          AND NOT a.attisdropped
        ORDER BY c.relname
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
        -- Permissive policies are OR-ed: any other permissive policy (for
        -- example the fail-open tms_* policies from migration 149) would
        -- re-open the table. tenant_isolation is the only permissive policy
        -- allowed on a company_id table; restrictive policies are kept.
        FOR p IN
            SELECT pol.policyname
            FROM pg_policies pol
            WHERE pol.schemaname = 'public'
              AND pol.tablename = t
              AND pol.policyname <> 'tenant_isolation'
              AND pol.permissive = 'PERMISSIVE'
        LOOP
            EXECUTE format('DROP POLICY IF EXISTS %I ON %I', p, t);
        END LOOP;
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I USING ({predicate_sql}) WITH CHECK ({predicate_sql})',
            t
        );
    END LOOP;
END
$$;
"""


async def pin_tenant(db, company_id: UUID | str) -> None:
    """Pin the current transaction to one company and clear rls_bypass."""
    await db.execute(
        text("SELECT set_config('app.current_company_id', :cid, true)"),
        {"cid": str(company_id)},
    )
    await db.execute(text("SELECT set_config('app.rls_bypass', '', true)"))
    current_company_id.set(company_id if isinstance(company_id, UUID) else UUID(str(company_id)))


async def clear_tenant(db) -> None:
    """Clear both transaction-local RLS settings."""
    await db.execute(text("SELECT set_config('app.current_company_id', '', true)"))
    await db.execute(text("SELECT set_config('app.rls_bypass', '', true)"))


@asynccontextmanager
async def system_scope(db, reason: str):
    """Enter an explicit transaction-local system scope for cross-tenant work.

    Settings are transaction-local, so a commit inside the block ends the
    system scope (fails closed); re-enter after a commit.
    """
    logger.debug("Entering system scope: %s", reason)
    await db.execute(text("SELECT set_config('app.rls_bypass', 'on', true)"))
    try:
        yield
    finally:
        try:
            await db.execute(text("SELECT set_config('app.rls_bypass', '', true)"))
        except Exception:  # noqa: BLE001
            # Only reachable when the transaction is already aborted; the
            # transaction-local setting disappears with its rollback.
            logger.debug("Could not clear system scope (transaction aborted)")


async def read_tenant_matview(db, view: str) -> list:
    """Read one materialized view for the currently pinned tenant.

    ``view`` must be in app.core.db_roles.MATERIALIZED_VIEWS. An unpinned
    session returns [] even inside system_scope because the query still
    applies the current_company_id predicate.
    """
    if view not in MATERIALIZED_VIEWS:
        raise ValueError(f"Unknown materialized view: {view}")
    result = await db.execute(
        text(
            f"SELECT * FROM {view} "
            "WHERE company_id::text = NULLIF(current_setting('app.current_company_id', true), '')"
        )
    )
    return result.mappings().all()

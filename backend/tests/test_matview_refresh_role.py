"""Materialized-view refresh role can refresh, app role cannot (issue #7).

Uses the same superuser engine pattern as test_reconcile_drift.py: a missing
TEST_SUPERUSER_DATABASE_URL fails in CI and skips locally. The test creates a
dedicated database, moves matview ownership to business_os_mvrefresh, and
verifies the refresh role can REFRESH CONCURRENTLY while business_os_app
cannot write to or refresh the matviews.
"""
import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.db_roles import MVREFRESH_ROLE, role_password
from app.core.migrate_schema import _ensure_managed_roles
from app.core.tenant_scope import (
    clear_tenant,
    pin_tenant,
    read_tenant_matview,
    tenant_rls_sql,
)

TEST_DATABASE = "business_os_mv_test"


def _superuser_url() -> str:
    url = os.environ.get("TEST_SUPERUSER_DATABASE_URL", "").strip()
    if url:
        return url
    if os.environ.get("CI"):
        pytest.fail("TEST_SUPERUSER_DATABASE_URL is required in CI")
    pytest.skip("TEST_SUPERUSER_DATABASE_URL is unset")


@pytest.mark.asyncio
async def test_matview_refresh_role_can_refresh_and_app_cannot():
    if not TEST_DATABASE.endswith("_test"):
        raise RuntimeError("matview refresh test database name must end with _test")

    super_url = make_url(_superuser_url())
    admin = create_async_engine(
        super_url.set(database="postgres"),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    drift = create_async_engine(
        super_url.set(database=TEST_DATABASE),
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
                text(f"DROP DATABASE IF EXISTS {TEST_DATABASE} WITH (FORCE)")
            )
            await conn.execute(text(f"CREATE DATABASE {TEST_DATABASE}"))

        async with drift.begin() as conn:
            await conn.execute(
                text(
                    """
                    CREATE TABLE invoices (
                        id uuid PRIMARY KEY,
                        company_id uuid NOT NULL,
                        invoice_date date,
                        status text,
                        total numeric
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE customer_receivables (
                        id uuid PRIMARY KEY,
                        company_id uuid NOT NULL,
                        status text,
                        outstanding_amount numeric
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE inventory_balances (
                        id uuid PRIMARY KEY,
                        company_id uuid NOT NULL,
                        warehouse_id uuid,
                        product_id uuid,
                        quantity numeric
                    )
                    """
                )
            )
            await conn.execute(text(tenant_rls_sql()))

            # Migration 060 matviews, with unique indexes for CONCURRENTLY.
            await conn.execute(
                text(
                    """
                    CREATE MATERIALIZED VIEW mv_sales_daily AS
                    SELECT
                        company_id,
                        invoice_date::date AS day,
                        COUNT(*) AS invoice_count,
                        SUM(total) AS total_amount
                    FROM invoices
                    WHERE status = 'issued'
                    GROUP BY company_id, invoice_date::date
                    """
                )
            )
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_mv_sales_daily "
                    "ON mv_sales_daily (company_id, day)"
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE MATERIALIZED VIEW mv_receivables_aging AS
                    SELECT
                        company_id,
                        status,
                        COUNT(*) AS receivable_count,
                        SUM(outstanding_amount) AS outstanding_total,
                        SUM(CASE WHEN status = 'overdue' THEN outstanding_amount ELSE 0 END) AS overdue_total
                    FROM customer_receivables
                    GROUP BY company_id, status
                    """
                )
            )
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_mv_receivables_aging "
                    "ON mv_receivables_aging (company_id, status)"
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE MATERIALIZED VIEW mv_stock_balances AS
                    SELECT
                        ib.company_id,
                        ib.warehouse_id,
                        ib.product_id,
                        SUM(ib.quantity) AS quantity
                    FROM inventory_balances ib
                    GROUP BY ib.company_id, ib.warehouse_id, ib.product_id
                    """
                )
            )
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_mv_stock_balances "
                    "ON mv_stock_balances (company_id, warehouse_id, product_id)"
                )
            )
            # Legacy state: migration 065 gave business_os_app ownership.
            for view in ("mv_sales_daily", "mv_receivables_aging", "mv_stock_balances"):
                await conn.execute(
                    text(f"ALTER MATERIALIZED VIEW {view} OWNER TO business_os_app")
                )

        await _ensure_managed_roles(drift, roles_only=False)

        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        warehouse_a = uuid.uuid4()
        product_a = uuid.uuid4()

        async with drift.begin() as conn:
            # One row per source table for company A and company B.
            await conn.execute(
                text(
                    """
                    INSERT INTO invoices (id, company_id, invoice_date, status, total)
                    VALUES
                        (:id1, :a, CURRENT_DATE, 'issued', 100),
                        (:id2, :b, CURRENT_DATE, 'issued', 200)
                    """
                ),
                {"id1": uuid.uuid4(), "id2": uuid.uuid4(), "a": company_a, "b": company_b},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO customer_receivables (id, company_id, status, outstanding_amount)
                    VALUES
                        (:id1, :a, 'open', 50),
                        (:id2, :b, 'open', 60)
                    """
                ),
                {"id1": uuid.uuid4(), "id2": uuid.uuid4(), "a": company_a, "b": company_b},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO inventory_balances (id, company_id, warehouse_id, product_id, quantity)
                    VALUES
                        (:id1, :a, :warehouse, :product, 10),
                        (:id2, :b, :warehouse, :product, 20)
                    """
                ),
                {
                    "id1": uuid.uuid4(),
                    "id2": uuid.uuid4(),
                    "a": company_a,
                    "b": company_b,
                    "warehouse": warehouse_a,
                    "product": product_a,
                },
            )

        refresh_password = role_password(MVREFRESH_ROLE)
        refresh_url = super_url.set(
            database=TEST_DATABASE,
            username=MVREFRESH_ROLE.name,
            password=refresh_password,
        )
        refresh_engine = create_async_engine(refresh_url, poolclass=NullPool)
        try:
            async with refresh_engine.begin() as conn:
                for view in ("mv_sales_daily", "mv_receivables_aging", "mv_stock_balances"):
                    await conn.execute(
                        text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
                    )
                    result = await conn.execute(text(f"SELECT company_id FROM {view}"))
                    companies = {row[0] for row in result}
                    assert company_a in companies
                    assert company_b in companies
        finally:
            await refresh_engine.dispose()

        app_test_url = os.getenv(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://business_os_app:business_os_app@postgres:5432/business_os_test",
        )
        app_url = make_url(app_test_url).set(database=TEST_DATABASE)
        app_engine = create_async_engine(app_url, poolclass=NullPool)
        try:
            # App role cannot refresh the matview.
            with pytest.raises(Exception):
                async with app_engine.begin() as conn:
                    await conn.execute(
                        text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sales_daily")
                    )

            # App role cannot insert into the matview.
            with pytest.raises(Exception):
                async with app_engine.begin() as conn:
                    await conn.execute(
                        text(
                            "INSERT INTO mv_sales_daily "
                            "(company_id, day, invoice_count, total_amount) "
                            "VALUES (:company_id, CURRENT_DATE, 1, 0)"
                        ),
                        {"company_id": company_a},
                    )

            # Unpinned app reads see zero matview rows.
            async with app_engine.begin() as conn:
                await clear_tenant(conn)
                for view in ("mv_sales_daily", "mv_receivables_aging", "mv_stock_balances"):
                    rows = await read_tenant_matview(conn, view)
                    assert rows == []

            # Pinned A sees only A rows; pinned B sees only B rows.
            for view in ("mv_sales_daily", "mv_receivables_aging", "mv_stock_balances"):
                async with app_engine.begin() as conn:
                    await pin_tenant(conn, company_a)
                    rows = await read_tenant_matview(conn, view)
                    assert rows
                    assert all(row["company_id"] == company_a for row in rows)

                async with app_engine.begin() as conn:
                    await pin_tenant(conn, company_b)
                    rows = await read_tenant_matview(conn, view)
                    assert rows
                    assert all(row["company_id"] == company_b for row in rows)

            # Unpinned app reads see zero source rows.
            async with app_engine.begin() as conn:
                await clear_tenant(conn)
                count = (
                    await conn.execute(text("SELECT count(*) FROM invoices"))
                ).scalar_one()
                assert count == 0

            # business_os_app no longer has TEMPORARY.
            async with app_engine.begin() as conn:
                has_temp = (
                    await conn.execute(
                        text(
                            "SELECT has_database_privilege(current_user, current_database(), 'TEMP')"
                        )
                    )
                ).scalar_one()
                assert has_temp is False
        finally:
            await app_engine.dispose()
    finally:
        await drift.dispose()
        async with admin.connect() as conn:
            await conn.execute(
                text(f"DROP DATABASE IF EXISTS {TEST_DATABASE} WITH (FORCE)")
            )
        await admin.dispose()

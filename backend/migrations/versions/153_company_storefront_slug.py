"""153_company_storefront_slug

Revision ID: 153_company_storefront_slug
Revises: 152_rls_fail_closed
Create Date: 2026-09-30

Adds storefront_slug and storefront_domain to companies for tenant-scoped
public storefront resolution. Idempotent like other migrations that use
inspect.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "153_company_storefront_slug"
down_revision = "152_rls_fail_closed"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    insp = inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def _index_exists(table: str, index: str) -> bool:
    insp = inspect(op.get_bind())
    return index in {i["name"] for i in insp.get_indexes(table)}


def _unique_on_column_exists(table: str, column: str) -> bool:
    """Return True when a single-column unique constraint/index already exists
    on ``column``. Avoids creating a duplicate of the model's implicit
    ``companies_storefront_domain_key`` constraint.
    """
    bind = op.get_bind()
    constraint_exists = bind.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_constraint con
                JOIN pg_class c ON c.oid = con.conrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(con.conkey)
                WHERE n.nspname = 'public'
                  AND c.relname = :table
                  AND con.contype = 'u'
                  AND array_length(con.conkey, 1) = 1
                  AND a.attname = :column
            )
            """
        ),
        {"table": table, "column": column},
    ).scalar()
    if constraint_exists:
        return True

    index_exists = bind.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
                WHERE n.nspname = 'public'
                  AND c.relname = :table
                  AND i.indisunique
                  AND i.indnkeyatts = 1
                  AND a.attname = :column
            )
            """
        ),
        {"table": table, "column": column},
    ).scalar()
    return bool(index_exists)


def upgrade() -> None:
    if not _column_exists("companies", "storefront_slug"):
        op.add_column(
            "companies",
            sa.Column("storefront_slug", sa.String(63), nullable=True),
        )
    if not _column_exists("companies", "storefront_domain"):
        op.add_column(
            "companies",
            sa.Column("storefront_domain", sa.String(255), nullable=True),
        )

    if not _index_exists("companies", "ix_companies_storefront_slug"):
        op.create_index(
            "ix_companies_storefront_slug",
            "companies",
            ["storefront_slug"],
            unique=True,
        )

    if not _unique_on_column_exists("companies", "storefront_domain"):
        op.create_unique_constraint(
            "companies_storefront_domain_key",
            "companies",
            ["storefront_domain"],
        )


def downgrade() -> None:
    if _index_exists("companies", "ix_companies_storefront_slug"):
        op.drop_index("ix_companies_storefront_slug", table_name="companies")

    op.execute(
        "ALTER TABLE companies DROP CONSTRAINT IF EXISTS companies_storefront_domain_key"
    )
    op.execute("DROP INDEX IF EXISTS companies_storefront_domain_key")

    if _column_exists("companies", "storefront_slug"):
        op.drop_column("companies", "storefront_slug")
    if _column_exists("companies", "storefront_domain"):
        op.drop_column("companies", "storefront_domain")

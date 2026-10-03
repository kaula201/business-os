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
from sqlalchemy import inspect

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


def _unique_constraint_exists(table: str, constraint: str) -> bool:
    insp = inspect(op.get_bind())
    return constraint in {c["name"] for c in insp.get_unique_constraints(table)}


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

    if not _unique_constraint_exists("companies", "uq_companies_storefront_domain"):
        op.create_unique_constraint(
            "uq_companies_storefront_domain",
            "companies",
            ["storefront_domain"],
        )


def downgrade() -> None:
    if _index_exists("companies", "ix_companies_storefront_slug"):
        op.drop_index("ix_companies_storefront_slug", table_name="companies")

    if _unique_constraint_exists("companies", "uq_companies_storefront_domain"):
        op.drop_constraint("uq_companies_storefront_domain", "companies", type_="unique")

    if _column_exists("companies", "storefront_slug"):
        op.drop_column("companies", "storefront_slug")
    if _column_exists("companies", "storefront_domain"):
        op.drop_column("companies", "storefront_domain")

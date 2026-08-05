"""Transfer materialized views to the app role for CONCURRENTLY refresh.

Revision ID: 065_mv_owner_app_role
Revises: 064_rls_policy_empty_scope
Create Date: 2026-08-05

REFRESH MATERIALIZED VIEW CONCURRENTLY requires owner privileges (or
UPDATE). The views were created by the superuser role during migration 060;
transfer them to business_os_app so the scheduled refresh script
(scripts/refresh_mvs.sh) can run them.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "065_mv_owner_app_role"
down_revision: Union[str, None] = "064_rls_policy_empty_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MATERIALIZED_VIEWS = ["mv_sales_daily", "mv_receivables_aging", "mv_stock_balances"]


def upgrade() -> None:
    for mv in MATERIALIZED_VIEWS:
        op.execute(f"ALTER MATERIALIZED VIEW {mv} OWNER TO business_os_app")


def downgrade() -> None:
    for mv in MATERIALIZED_VIEWS:
        op.execute(f"ALTER MATERIALIZED VIEW {mv} OWNER TO business_os")

"""Backfill BASE company_modules rows for existing companies (#24).

Revision ID: 155_backfill_base_company_modules
Revises: 154_invoice_payments
Create Date: 2026-10-12

Since #44 a missing company_modules row means "disabled", and since #45
register seeds the BASE rows for new companies. Companies created before #45
may still have no BASE rows. This data migration inserts only the missing
BASE rows (settings, clients) as enabled. It never creates or changes a row
for a paid module, and never touches an existing row (enabled or disabled),
so no company gains a paid module it did not have (REQ-PKG / AC-PKG).

RLS stays fail-closed: each company is pinned with a transaction-local
app.current_company_id; app.rls_bypass is not used. Idempotent.
"""

from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "155_backfill_base_company_modules"
down_revision = "154_invoice_payments"
branch_labels = None
depends_on = None

# Base module codes that are always enabled for every company.
# Frozen here intentionally; do not import application code.
BASE_CODES = ("settings", "clients")


def backfill_base_company_modules(bind: Connection) -> int:
    """
    Backfill missing `company_modules` rows for existing companies.

    Inserts only BASE modules that are active and currently missing for a company.
    Existing rows, whether enabled or disabled, are never modified.
    Paid modules are never inserted or enabled.
    The function is idempotent and safe under RLS.
    """

    inserted_total = 0

    # Get all company IDs. companies is not RLS-protected.
    company_ids = bind.execute(
        text("SELECT id::text FROM companies")
    ).scalars().all()

    for cid in company_ids:
        # Pin the current company so RLS policy allows access to
        # company_modules for this company.
        bind.execute(
            text("SELECT set_config('app.current_company_id', :cid, true)"),
            {"cid": cid},
        )

        result = bind.execute(
            text(
                """
                INSERT INTO company_modules (id, company_id, module_id, enabled)
                SELECT gen_random_uuid(), CAST(:cid AS uuid), am.id, true
                FROM app_modules am
                WHERE am.code = ANY(:codes)
                  AND am.is_active = true
                  AND NOT EXISTS (
                      SELECT 1
                      FROM company_modules cm
                      WHERE cm.company_id = CAST(:cid AS uuid)
                        AND cm.module_id = am.id
                  )
                ON CONFLICT ON CONSTRAINT uq_company_module DO NOTHING
                """
            ),
            {"cid": cid, "codes": list(BASE_CODES)},
        )

        rowcount = result.rowcount
        if rowcount and rowcount > 0:
            inserted_total += rowcount

    # Unpin so later statements in this transaction are not tenant-scoped.
    bind.execute(text("SELECT set_config('app.current_company_id', '', true)"))

    return inserted_total


def upgrade():
    bind = op.get_bind()
    backfill_base_company_modules(bind)


def downgrade():
    # No-op: we do not remove the backfilled rows because they may have been
    # modified by operators after the backfill.
    pass

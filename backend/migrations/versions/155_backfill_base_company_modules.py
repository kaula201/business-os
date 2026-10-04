"""155_backfill_base_company_modules

Revision ID: 155_backfill_base_company_modules
Revises: 154_invoice_payments
Create Date: 2026-10-04

#24 item 3 — give every existing company its BASE entitlements.

Register now seeds BASE rows for new companies (#45), but companies created
before that, and any company left with no rows at all, still have nothing. The
dev database shows the shape: app_modules=64, company_modules=0.

Now that a missing row means disabled (#44), those companies would own nothing
and even their own admin would hit fail-closed paths.

Idempotent by construction: ON CONFLICT DO NOTHING against uq_company_module, so
re-running is a no-op and an explicit operator disable is never overwritten.

Runs as the migration superuser, which bypasses RLS, so the cross-tenant insert
is allowed. This is migration-only; no application code runs unpinned.
"""
from alembic import op
from sqlalchemy import text

revision = "155_backfill_base_company_modules"
down_revision = "154_invoice_payments"
branch_labels = None
depends_on = None

# Keep in sync with app.core.modules.BASE_MODULE_CODES. Inlined rather than
# imported because migrations must stay pinned to the schema of their revision;
# importing app code would make an old migration change meaning when constants
# move. A drift test asserts the two stay equal.
BASE_MODULE_CODES = ("settings", "clients")


def upgrade() -> None:
    bind = op.get_bind()

    # Guard: skip cleanly if the catalog has not been seeded yet in this database.
    # seed_modules() runs at application startup, but a bare migration run (CI,
    # fresh volume) may not have it, and inserting module ids that do not exist
    # would fail the FK.
    catalog_codes = {
        row[0]
        for row in bind.execute(
            text("SELECT code FROM app_modules WHERE is_active = true")
        )
    }
    codes = [code for code in BASE_MODULE_CODES if code in catalog_codes]
    if not codes:
        return

    bind.execute(
        text(
            """
            INSERT INTO company_modules (id, company_id, module_id, enabled, created_at, updated_at)
            SELECT gen_random_uuid(), c.id, m.id, true, now(), now()
            FROM companies c
            CROSS JOIN app_modules m
            WHERE m.code = ANY(:codes)
              AND m.is_active = true
            ON CONFLICT ON CONSTRAINT uq_company_module DO NOTHING
            """
        ),
        {"codes": codes},
    )


def downgrade() -> None:
    """Remove only the BASE rows, and only where the module is still BASE.

    Deliberately narrow: dropping every BASE row could remove an entitlement an
    operator granted on purpose after this migration ran, so the downgrade is
    documented as best-effort rather than perfectly reversible.
    """
    bind = op.get_bind()
    bind.execute(
        text(
            """
            DELETE FROM company_modules cm
            USING app_modules m
            WHERE cm.module_id = m.id
              AND m.code = ANY(:codes)
            """
        ),
        {"codes": list(BASE_MODULE_CODES)},
    )

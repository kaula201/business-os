"""101_tender_child_rls

Revision ID: 101_tender_child_rls
Revises: 100_tenders
Create Date: 2026-08-18

Apply tenant RLS to tender child tables (defense-in-depth).
"""
from alembic import op

revision = "101_tender_child_rls"
down_revision = "100_tenders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    parent_policy = ("tender_id IN (SELECT id FROM tenders WHERE company_id::text = "
                     "current_setting('app.current_company_id', true))")
    # tender_lines and tender_bids reference tenders directly.
    for table in ("tender_lines", "tender_bids"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'CREATE POLICY "{table}_tenant_policy" ON "{table}" USING ({parent_policy}) WITH CHECK ({parent_policy})')
    # tender_bid_lines references tender_bids (which is already tenant-scoped).
    bid_policy = ("bid_id IN (SELECT id FROM tender_bids WHERE tender_id IN "
                  "(SELECT id FROM tenders WHERE company_id::text = "
                  "current_setting('app.current_company_id', true)))")
    op.execute('ALTER TABLE "tender_bid_lines" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "tender_bid_lines" FORCE ROW LEVEL SECURITY')
    op.execute(f'CREATE POLICY "tender_bid_lines_tenant_policy" ON "tender_bid_lines" USING ({bid_policy}) WITH CHECK ({bid_policy})')


def downgrade() -> None:
    for table in ("tender_bid_lines", "tender_bids", "tender_lines"):
        op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_policy" ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')

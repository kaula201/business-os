"""098_fiscal_tenant_guard

Revision ID: 098_fiscal_tenant_guard
Revises: 097_fiscal_application
Create Date: 2026-08-18

DB-level tenant guard for fiscal position references.
"""
from alembic import op

revision = "098_fiscal_tenant_guard"
down_revision = "097_fiscal_application"
branch_labels = None
depends_on = None

TABLES = ("clients", "suppliers", "purchase_orders", "supplier_invoices", "invoices")


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION enforce_fiscal_position_tenant() RETURNS trigger AS $$
    BEGIN
      IF NEW.fiscal_position_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM fiscal_positions fp WHERE fp.id = NEW.fiscal_position_id AND fp.company_id = NEW.company_id
      ) THEN RAISE EXCEPTION 'fiscal_position_id must belong to the same company'; END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    """)
    for table in TABLES:
        op.execute(f"CREATE TRIGGER trg_{table}_fiscal_tenant BEFORE INSERT OR UPDATE OF fiscal_position_id, company_id ON {table} FOR EACH ROW EXECUTE FUNCTION enforce_fiscal_position_tenant()")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_fiscal_tenant ON {table}")
    op.execute("DROP FUNCTION IF EXISTS enforce_fiscal_position_tenant()")

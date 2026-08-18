"""100_tenders

Revision ID: 100_tenders
Revises: 099_consolidation_elims
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "100_tenders"
down_revision = "099_consolidation_elims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("tender_number", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("required_date", sa.Date()),
        sa.Column("budget_amount", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GEL"),
        sa.Column("awarded_supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tenders_company_id", "tenders", ["company_id"])
    op.create_index("ix_tenders_status", "tenders", ["status"])

    op.create_table(
        "tender_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("expected_price", sa.Numeric(18, 4)),
    )
    op.create_index("ix_tender_lines_tender_id", "tender_lines", ["tender_id"])

    op.create_table(
        "tender_bids",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GEL"),
        sa.Column("delivery_days", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tender_id", "supplier_id", name="uq_tender_bid_supplier"),
    )
    op.create_index("ix_tender_bids_tender_id", "tender_bids", ["tender_id"])
    op.create_index("ix_tender_bids_supplier_id", "tender_bids", ["supplier_id"])

    op.create_table(
        "tender_bid_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bid_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tender_bids.id"), nullable=False),
        sa.Column("tender_line_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tender_lines.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GEL"),
        sa.Column("delivery_days", sa.Integer()),
    )
    op.create_index("ix_tender_bid_lines_bid_id", "tender_bid_lines", ["bid_id"])

    policy = "company_id::text = current_setting('app.current_company_id', true)"
    op.execute('ALTER TABLE "tenders" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "tenders" FORCE ROW LEVEL SECURITY')
    op.execute(f'CREATE POLICY "tenders_tenant_policy" ON "tenders" USING ({policy}) WITH CHECK ({policy})')
    # Child-table RLS is applied by migration 101_tender_child_rls.


def downgrade() -> None:
    op.drop_table("tender_bid_lines")
    op.drop_table("tender_bids")
    op.drop_table("tender_lines")
    op.drop_table("tenders")

"""148_tms_freight_invoice

Revision ID: 148_tms_freight_invoice
Revises: 147_tms_gps
Create Date: 2026-09-21

Standalone freight invoice per trip (client-billable shipping charge), kept
FIN-independent so the TMS module sells standalone (FIN link optional).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "148_tms_freight_invoice"
down_revision = "147_tms_gps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tms_freight_invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("tms_trips.id"), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="issued"),
        sa.Column("issued_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GEL"),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("freight_charge", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("carrier_rate", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("margin", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("lines", JSONB(), nullable=False),
        sa.Column("fin_invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tms_freight_inv_trip", "tms_freight_invoices", ["trip_id"])


def downgrade() -> None:
    op.drop_index("ix_tms_freight_inv_trip", table_name="tms_freight_invoices")
    op.drop_table("tms_freight_invoices")

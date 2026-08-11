"""077_email_tracking_signatures

Revision ID: 077_email_tracking_signatures
Revises: 076_sales_teams
Create Date: 2026-08-11

Email tracking events + signature requests.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "077_email_tracking_signatures"
down_revision: str | None = "076_sales_teams"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("campaign_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("email_campaigns.id"), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_email_events_company_id", "email_events", ["company_id"])
    op.create_index("ix_email_events_campaign_id", "email_events", ["campaign_id"])
    op.create_index("ix_email_events_event_type", "email_events", ["event_type"])

    op.create_table(
        "signature_requests",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("document_name", sa.String(255), nullable=False),
        sa.Column("document_url", sa.String(500), nullable=True),
        sa.Column("signer_name", sa.String(255), nullable=False),
        sa.Column("signer_email", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("signing_token", sa.String(64), nullable=False),
        sa.Column("signed_at", sa.DateTime(), nullable=True),
        sa.Column("signed_by_email", sa.String(255), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_signature_requests_company_id", "signature_requests", ["company_id"])
    op.create_index("ix_signature_requests_signer_email", "signature_requests", ["signer_email"])
    op.create_index("ix_signature_requests_status", "signature_requests", ["status"])
    op.create_index("ix_signature_requests_signing_token", "signature_requests", ["signing_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_signature_requests_signing_token", table_name="signature_requests")
    op.drop_index("ix_signature_requests_status", table_name="signature_requests")
    op.drop_index("ix_signature_requests_signer_email", table_name="signature_requests")
    op.drop_index("ix_signature_requests_company_id", table_name="signature_requests")
    op.drop_table("signature_requests")
    op.drop_index("ix_email_events_event_type", table_name="email_events")
    op.drop_index("ix_email_events_campaign_id", table_name="email_events")
    op.drop_index("ix_email_events_company_id", table_name="email_events")
    op.drop_table("email_events")

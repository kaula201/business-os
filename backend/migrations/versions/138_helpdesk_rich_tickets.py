"""138_helpdesk_rich_tickets

Revision ID: 138_helpdesk_rich_tickets
Revises: 137_pos_customer_deposit
Create Date: 2026-08-24

Rich ticket fields (category, source, tags, related, time, satisfaction)
+ followers, messages (email thread/portal), real attachments.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "138_helpdesk_rich_tickets"
down_revision = "137_pos_customer_deposit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("helpdesk_tickets", sa.Column("category", sa.String(50), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("ticket_type", sa.String(50), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("source_channel", sa.String(30), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("tags", JSONB(), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("related_product_id", sa.UUID(), sa.ForeignKey("products.id"), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("related_invoice_id", sa.UUID(), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("related_order_id", sa.UUID(), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("time_spent_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("helpdesk_tickets", sa.Column("satisfaction_score", sa.Integer(), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("satisfaction_comment", sa.Text(), nullable=True))

    op.create_table(
        "helpdesk_followers",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("ticket_id", sa.UUID(), sa.ForeignKey("helpdesk_tickets.id"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_helpdesk_followers_ticket", "helpdesk_followers", ["ticket_id"])

    op.create_table(
        "helpdesk_messages",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("ticket_id", sa.UUID(), sa.ForeignKey("helpdesk_tickets.id"), nullable=False),
        sa.Column("author_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column("direction", sa.String(10), nullable=False, server_default="inbound"),
        sa.Column("channel", sa.String(20), nullable=False, server_default="email"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_helpdesk_messages_ticket", "helpdesk_messages", ["ticket_id"])

    op.create_table(
        "helpdesk_attachments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("ticket_id", sa.UUID(), sa.ForeignKey("helpdesk_tickets.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False, server_default="application/octet-stream"),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("uploaded_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_helpdesk_attachments_ticket", "helpdesk_attachments", ["ticket_id"])


def downgrade() -> None:
    op.drop_table("helpdesk_attachments")
    op.drop_table("helpdesk_messages")
    op.drop_table("helpdesk_followers")
    op.drop_column("helpdesk_tickets", "satisfaction_comment")
    op.drop_column("helpdesk_tickets", "satisfaction_score")
    op.drop_column("helpdesk_tickets", "time_spent_minutes")
    op.drop_column("helpdesk_tickets", "related_order_id")
    op.drop_column("helpdesk_tickets", "related_invoice_id")
    op.drop_column("helpdesk_tickets", "related_product_id")
    op.drop_column("helpdesk_tickets", "tags")
    op.drop_column("helpdesk_tickets", "source_channel")
    op.drop_column("helpdesk_tickets", "ticket_type")
    op.drop_column("helpdesk_tickets", "category")

"""078_subscription_renewal

Revision ID: 078_subscription_renewal
Revises: 077_email_tracking_signatures
Create Date: 2026-08-11

Subscription next_billing_date + renewal support.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "078_subscription_renewal"
down_revision: str | None = "077_email_tracking_signatures"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("next_billing_date", sa.Date(), nullable=True))
    op.create_index("ix_subscriptions_next_billing_date", "subscriptions", ["next_billing_date"])


def downgrade() -> None:
    op.drop_index("ix_subscriptions_next_billing_date", table_name="subscriptions")
    op.drop_column("subscriptions", "next_billing_date")

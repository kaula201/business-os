"""140_api_webhook_hardening

Revision ID: 140_api_webhook_hardening
Revises: 139_security_sessions_audit
Create Date: 2026-08-24

API keys: branch scope, resource-level, allowed IPs, rate limits.
Webhooks: retry/backoff; events: dead-letter, idempotency, next retry.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "140_api_webhook_hardening"
down_revision = "139_security_sessions_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("branch_id", sa.UUID(), nullable=True))
    op.add_column("api_keys", sa.Column("resource_ids", JSONB(), nullable=True))
    op.add_column("api_keys", sa.Column("allowed_ips", JSONB(), nullable=True))
    op.add_column("api_keys", sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="120"))
    op.add_column("api_keys", sa.Column("rate_window_start", sa.DateTime(), nullable=True))
    op.add_column("api_keys", sa.Column("rate_window_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_api_keys_branch", "api_keys", ["branch_id"])

    op.add_column("webhooks", sa.Column("retry_max", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("webhooks", sa.Column("retry_backoff_seconds", sa.Integer(), nullable=False, server_default="60"))

    op.add_column("webhook_events", sa.Column("next_retry_at", sa.DateTime(), nullable=True))
    op.add_column("webhook_events", sa.Column("idempotency_key", sa.String(64), nullable=True))
    op.create_index("ix_webhook_events_idempotency", "webhook_events", ["idempotency_key"])


def downgrade() -> None:
    op.drop_index("ix_webhook_events_idempotency", table_name="webhook_events")
    op.drop_column("webhook_events", "idempotency_key")
    op.drop_column("webhook_events", "next_retry_at")
    op.drop_column("webhooks", "retry_backoff_seconds")
    op.drop_column("webhooks", "retry_max")
    op.drop_index("ix_api_keys_branch", table_name="api_keys")
    op.drop_column("api_keys", "rate_window_count")
    op.drop_column("api_keys", "rate_window_start")
    op.drop_column("api_keys", "rate_limit_per_minute")
    op.drop_column("api_keys", "allowed_ips")
    op.drop_column("api_keys", "resource_ids")
    op.drop_column("api_keys", "branch_id")

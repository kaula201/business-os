"""139_security_sessions_audit

Revision ID: 139_security_sessions_audit
Revises: 138_helpdesk_rich_tickets
Create Date: 2026-08-24

Login history: device/geo/session fields; audit log: old/new values + user name.
"""
import sqlalchemy as sa
from alembic import op

revision = "139_security_sessions_audit"
down_revision = "138_helpdesk_rich_tickets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("login_history", sa.Column("device_name", sa.String(120), nullable=True))
    op.add_column("login_history", sa.Column("os_name", sa.String(60), nullable=True))
    op.add_column("login_history", sa.Column("device_type", sa.String(20), nullable=True))
    op.add_column("login_history", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("login_history", sa.Column("country", sa.String(60), nullable=True))
    op.add_column("login_history", sa.Column("session_key", sa.String(64), nullable=True))
    op.add_column("login_history", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("login_history", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.add_column("login_history", sa.Column("revoked_at", sa.DateTime(), nullable=True))
    op.create_index("ix_login_history_session_key", "login_history", ["session_key"])

    op.add_column("audit_logs", sa.Column("user_name", sa.String(255), nullable=True))
    op.add_column("audit_logs", sa.Column("entity_label", sa.String(255), nullable=True))
    op.add_column("audit_logs", sa.Column("field_name", sa.String(100), nullable=True))
    op.add_column("audit_logs", sa.Column("old_value", sa.Text(), nullable=True))
    op.add_column("audit_logs", sa.Column("new_value", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_logs", "new_value")
    op.drop_column("audit_logs", "old_value")
    op.drop_column("audit_logs", "field_name")
    op.drop_column("audit_logs", "entity_label")
    op.drop_column("audit_logs", "user_name")
    op.drop_index("ix_login_history_session_key", table_name="login_history")
    op.drop_column("login_history", "revoked_at")
    op.drop_column("login_history", "last_seen_at")
    op.drop_column("login_history", "is_active")
    op.drop_column("login_history", "session_key")
    op.drop_column("login_history", "country")
    op.drop_column("login_history", "city")
    op.drop_column("login_history", "device_type")
    op.drop_column("login_history", "os_name")
    op.drop_column("login_history", "device_name")

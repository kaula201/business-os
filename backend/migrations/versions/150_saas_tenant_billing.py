"""150_saas_tenant_billing

Revision ID: 150_saas_tenant_billing
Revises: 149_tms_tenant_rls_and_driver_account
Create Date: 2026-09-27

SaaS tenant billing — the platform's OWN subscription model (distinct from
the vendor-internal `subscriptions` tables). Adds:

1. tenant_plans        — sellable catalog with feature-limit JSONB
2. tenant_subscriptions — a company's platform subscription (trial → active → …)

Feature limits gate TMS at runtime (drivers/vehicles/trips caps, geocoder/ETA/
live-map toggles) so the TMS module can be sold standalone.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "150_saas_tenant_billing"
down_revision = "149_tms_tenant_rls_and_driver_account"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("feature_limits", JSONB, nullable=False, server_default="{}"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_plans_code", "tenant_plans", ["code"], unique=True)

    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("tenant_plans.id"), nullable=False),
        sa.Column("plan_code", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("feature_limits", JSONB, nullable=False, server_default="{}"),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("trial_ends_at", sa.Date, nullable=True),
        sa.Column("next_billing_date", sa.Date, nullable=True),
        sa.Column("last_billed_at", sa.DateTime, nullable=True),
        sa.Column("cancelled_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_subscriptions_company", "tenant_subscriptions", ["company_id"], unique=True)
    op.create_index("ix_tenant_subscriptions_plan", "tenant_subscriptions", ["plan_id"])
    op.create_index("ix_tenant_subscriptions_plan_code", "tenant_subscriptions", ["plan_code"])
    op.create_index("ix_tenant_subscriptions_status", "tenant_subscriptions", ["status"])

    # Seed the default sellable plans (idempotent: skip if codes already exist).
    op.execute(
        """
        INSERT INTO tenant_plans (id, code, name, amount, frequency, feature_limits, is_active, sort_order)
        SELECT gen_random_uuid(), v.code, v.name, v.amount, 'monthly', v.feature_limits::jsonb, true, v.sort_order
        FROM (VALUES
          ('tms_starter',   'TMS Starter',    49.00,
           '{"max_drivers": 3, "max_vehicles": 5, "max_trips_month": 50, "geocoder": true, "eta": true, "live_map": true}', 1),
          ('tms_pro',       'TMS Pro',       149.00,
           '{"max_drivers": 15, "max_vehicles": 30, "max_trips_month": 500, "geocoder": true, "eta": true, "live_map": true}', 2),
          ('tms_enterprise','TMS Enterprise',399.00,
           '{"max_drivers": -1, "max_vehicles": -1, "max_trips_month": -1, "geocoder": true, "eta": true, "live_map": true}', 3)
        ) AS v(code, name, amount, feature_limits, sort_order)
        WHERE NOT EXISTS (SELECT 1 FROM tenant_plans WHERE code = v.code);
        """
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_subscriptions_status", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_plan_code", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_plan", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_company", table_name="tenant_subscriptions")
    op.drop_table("tenant_subscriptions")
    op.drop_index("ix_tenant_plans_code", table_name="tenant_plans")
    op.drop_table("tenant_plans")

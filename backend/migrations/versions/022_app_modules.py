"""Create app_modules, company_modules, module_permissions tables.

Revision ID: 022_app_modules
Revises: 021_fleet_vehicle_locations
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022_app_modules"
down_revision: Union[str, None] = "021_fleet_vehicle_locations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── AppModule catalog ──────────────────────────────────────────────
    op.create_table(
        "app_modules",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(100), nullable=True),
        sa.Column("route", sa.String(255), nullable=True),
        sa.Column("category", sa.String(50), server_default="other", nullable=False, index=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("depends_on", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── CompanyModule ─────────────────────────────────────────────────
    op.create_table(
        "company_modules",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("module_id", sa.UUID(as_uuid=True), sa.ForeignKey("app_modules.id"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "module_id", name="uq_company_module"),
    )

    # ── ModulePermission ──────────────────────────────────────────────
    op.create_table(
        "module_permissions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("module_id", sa.UUID(as_uuid=True), sa.ForeignKey("app_modules.id"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("can_access", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("can_create", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("can_edit", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("can_delete", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("can_approve", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("module_id", "role", name="uq_module_permission_role"),
    )


def downgrade() -> None:
    op.drop_table("module_permissions")
    op.drop_table("company_modules")
    op.drop_table("app_modules")

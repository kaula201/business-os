"""122_pos_restaurant_courses_floorplan

Revision ID: 122_pos_restaurant_courses_floorplan
Revises: 121_pos_loyalty_tiers_coupons
Create Date: 2026-08-20

Restaurant courses on order items and floor-plan coordinates on tables.
"""
import sqlalchemy as sa
from alembic import op

revision = "122_pos_restaurant_courses_floorplan"
down_revision = "121_pos_loyalty_tiers_coupons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_order_items", sa.Column("course", sa.String(20), nullable=False, server_default="main"))
    op.add_column("restaurant_tables", sa.Column("pos_x", sa.Integer(), nullable=True))
    op.add_column("restaurant_tables", sa.Column("pos_y", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("restaurant_tables", "pos_y")
    op.drop_column("restaurant_tables", "pos_x")
    op.drop_column("pos_order_items", "course")

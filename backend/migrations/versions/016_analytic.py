"""Add analytic accounting tables.
Revision ID: 016_analytic
Revises: 015_currency
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
revision: str = "016_analytic"
down_revision: Union[str, None] = "015_currency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table("analytic_accounts",
        sa.Column("id",sa.UUID(as_uuid=True),primary_key=True,server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id",sa.UUID(as_uuid=True),sa.ForeignKey("companies.id"),nullable=False,index=True),
        sa.Column("code",sa.String(30),nullable=False), sa.Column("name",sa.String(255),nullable=False),
        sa.Column("account_type",sa.String(30),server_default="cost_center",nullable=False),
        sa.Column("is_active",sa.Boolean(),server_default=sa.true(),nullable=False), sa.Column("notes",sa.Text()),
        sa.Column("created_at",sa.DateTime(),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("company_id","code",name="uq_analytic_account_code"))
    op.create_table("analytic_entries",
        sa.Column("id",sa.UUID(as_uuid=True),primary_key=True,server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id",sa.UUID(as_uuid=True),sa.ForeignKey("companies.id"),nullable=False,index=True),
        sa.Column("analytic_account_id",sa.UUID(as_uuid=True),sa.ForeignKey("analytic_accounts.id"),nullable=False,index=True),
        sa.Column("gl_account_id",sa.UUID(as_uuid=True),sa.ForeignKey("gl_accounts.id")),
        sa.Column("entry_date",sa.Date(),nullable=False,index=True), sa.Column("description",sa.String(500),nullable=False),
        sa.Column("amount",sa.Numeric(18,2),nullable=False), sa.Column("direction",sa.String(10),nullable=False),
        sa.Column("reference",sa.String(100)), sa.Column("created_at",sa.DateTime(),server_default=sa.func.now(),nullable=False))

def downgrade() -> None:
    op.drop_table("analytic_entries"); op.drop_table("analytic_accounts")

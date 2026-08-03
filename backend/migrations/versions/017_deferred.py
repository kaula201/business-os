"""Add deferred revenue/expense schedules.
Revision ID: 017_deferred
Revises: 016_analytic
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
revision: str = "017_deferred"
down_revision: Union[str, None] = "016_analytic"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table("deferred_schedules",
        sa.Column("id",sa.UUID(as_uuid=True),primary_key=True,server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id",sa.UUID(as_uuid=True),sa.ForeignKey("companies.id"),nullable=False,index=True),
        sa.Column("name",sa.String(255),nullable=False), sa.Column("deferral_type",sa.String(20),nullable=False),
        sa.Column("total_amount",sa.Numeric(18,2),nullable=False), sa.Column("start_date",sa.Date(),nullable=False),
        sa.Column("periods",sa.Integer(),nullable=False),
        sa.Column("source_gl_account_id",sa.UUID(as_uuid=True),sa.ForeignKey("gl_accounts.id"),nullable=False),
        sa.Column("recognition_gl_account_id",sa.UUID(as_uuid=True),sa.ForeignKey("gl_accounts.id"),nullable=False),
        sa.Column("status",sa.String(20),server_default="active",nullable=False), sa.Column("notes",sa.Text()),
        sa.Column("created_by",sa.UUID(as_uuid=True),sa.ForeignKey("users.id")),
        sa.Column("created_at",sa.DateTime(),server_default=sa.func.now(),nullable=False),
        sa.Column("updated_at",sa.DateTime(),server_default=sa.func.now(),nullable=False))
    op.create_table("deferred_recognitions",
        sa.Column("id",sa.UUID(as_uuid=True),primary_key=True,server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id",sa.UUID(as_uuid=True),sa.ForeignKey("companies.id"),nullable=False,index=True),
        sa.Column("schedule_id",sa.UUID(as_uuid=True),sa.ForeignKey("deferred_schedules.id"),nullable=False,index=True),
        sa.Column("period_no",sa.Integer(),nullable=False), sa.Column("recognition_date",sa.Date(),nullable=False,index=True),
        sa.Column("amount",sa.Numeric(18,2),nullable=False), sa.Column("status",sa.String(20),server_default="pending",nullable=False),
        sa.Column("journal_entry_id",sa.UUID(as_uuid=True),sa.ForeignKey("journal_entries.id")),
        sa.Column("recognized_by",sa.UUID(as_uuid=True),sa.ForeignKey("users.id")), sa.Column("recognized_at",sa.DateTime()),
        sa.Column("created_at",sa.DateTime(),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("schedule_id","period_no",name="uq_deferred_period"))

def downgrade() -> None:
    op.drop_table("deferred_recognitions"); op.drop_table("deferred_schedules")

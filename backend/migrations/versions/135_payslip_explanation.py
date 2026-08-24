"""135_payslip_explanation

Revision ID: 135_payslip_explanation
Revises: 134_employee_pension_participant
Create Date: 2026-08-24

Per-line legal explanation JSON on payslips.
"""
import sqlalchemy as sa
from alembic import op

revision = "135_payslip_explanation"
down_revision = "134_employee_pension_participant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payslips", sa.Column("explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("payslips", "explanation")

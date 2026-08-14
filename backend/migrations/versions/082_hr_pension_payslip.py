"""082_hr_pension_payslip

Revision ID: 082_hr_pension_payslip
Revises: 081_pos_enhanced
Create Date: 2026-08-14

HR: pension contribution on payroll entries + payslips.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "082_hr_pension_payslip"
down_revision: str | None = "081_pos_enhanced"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payroll_entries", sa.Column("pension_contribution", sa.Numeric(14, 2), nullable=False, server_default="0"))

    op.create_table(
        "payslips",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("employee_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("payroll_entry_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("payroll_entries.id"), nullable=False),
        sa.Column("payslip_number", sa.String(50), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("base_salary", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("gross_pay", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("additions", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("deductions", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("pension_contribution", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("income_tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("net_pay", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payslips_company_id", "payslips", ["company_id"])
    op.create_index("ix_payslips_employee_id", "payslips", ["employee_id"])
    op.create_index("ix_payslips_payroll_entry_id", "payslips", ["payroll_entry_id"])


def downgrade() -> None:
    op.drop_table("payslips")
    op.drop_column("payroll_entries", "pension_contribution")

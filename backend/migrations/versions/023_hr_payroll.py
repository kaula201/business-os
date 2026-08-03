"""Create HR / Payroll tables: departments, employees, payroll_entries, timesheets.

Revision ID: 023_hr_payroll
Revises: 022_app_modules
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023_hr_payroll"
down_revision: Union[str, None] = "022_app_modules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Employees (no FK to departments yet — added after) ────────────
    op.create_table(
        "employees",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("department_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("personal_number", sa.String(11), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("position", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("contract_type", sa.String(20), server_default="permanent", nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False, index=True),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("base_salary", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("salary_currency", sa.String(3), server_default="GEL", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "personal_number", name="uq_employee_personal_number"),
    )

    # ── Departments ────────────────────────────────────────────────────
    op.create_table(
        "departments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parent_id", sa.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("manager_id", sa.UUID(as_uuid=True), nullable=True),  # no FK — avoids circular dependency
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "code", name="uq_department_company_code"),
    )

    # Add FK for employee.department_id after departments exists
    op.create_foreign_key(
        "fk_employee_department", "employees", "departments",
        ["department_id"], ["id"],
    )

    # ── Payroll Entries ──────────────────────────────────────────────
    op.create_table(
        "payroll_entries",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("base_salary", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("gross_pay", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("additions", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("deductions", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("income_tax", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("net_pay", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "employee_id", "period_year", "period_month", name="uq_payroll_period"),
    )

    # ── Timesheets ───────────────────────────────────────────────────
    op.create_table(
        "timesheets",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("hours_worked", sa.Numeric(5, 2), server_default="8", nullable=False),
        sa.Column("overtime_hours", sa.Numeric(5, 2), server_default="0", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("employee_id", "work_date", name="uq_timesheet_employee_date"),
    )


def downgrade() -> None:
    op.drop_table("timesheets")
    op.drop_table("payroll_entries")
    op.drop_table("departments")
    op.drop_table("employees")

"""Enhance HR module: employee documents, leave tracking, attendance, performance reviews.

Adds tables: employee_documents, leave_types, leave_balances, leave_requests,
attendance_records, performance_reviews, performance_goals.
Also adds new columns to employees and departments.

Revision ID: 044_hr_enhance
Revises: 36268de3767d
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "044_hr_enhance"
down_revision: Union[str, None] = "36268de3767d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New columns on departments ──────────────────────────────────────────
    op.add_column("departments", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("departments", sa.Column("head_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("departments", sa.Column("budget", sa.Numeric(14, 2), nullable=True))

    # ── New columns on employees ────────────────────────────────────────────
    op.add_column("employees", sa.Column("gender", sa.String(20), nullable=True))
    op.add_column("employees", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("employees", sa.Column("emergency_contact_name", sa.String(255), nullable=True))
    op.add_column("employees", sa.Column("emergency_contact_phone", sa.String(50), nullable=True))
    op.add_column("employees", sa.Column("bank_account_number", sa.String(50), nullable=True))
    op.add_column("employees", sa.Column("bank_name", sa.String(255), nullable=True))
    op.add_column("employees", sa.Column("probation_end_date", sa.Date(), nullable=True))
    op.add_column("employees", sa.Column("contract_end_date", sa.Date(), nullable=True))
    op.add_column("employees", sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True))
    op.add_column("employees", sa.Column("manager_id", sa.Uuid(), nullable=True))

    # ── Employee Documents ───────────────────────────────────────────────────
    op.create_table(
        "employee_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("document_number", sa.String(100), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("issuing_authority", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "document_type", "document_number", name="uq_emp_doc_type_number"),
    )

    # ── Leave Types ─────────────────────────────────────────────────────────
    op.create_table(
        "leave_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("days_per_year", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_paid", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("requires_approval", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("carry_forward", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("max_consecutive_days", sa.Integer(), nullable=True),
        sa.Column("min_notice_days", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "code", name="uq_leave_type_company_code"),
    )

    # ── Leave Balances ──────────────────────────────────────────────────────
    op.create_table(
        "leave_balances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("leave_type_id", sa.Uuid(), sa.ForeignKey("leave_types.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("total_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("used_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pending_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("remaining_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("carried_forward", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "leave_type_id", "year", name="uq_leave_balance_emp_year"),
    )

    # ── Leave Requests ──────────────────────────────────────────────────────
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("leave_type_id", sa.Uuid(), sa.ForeignKey("leave_types.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("total_days", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False, index=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Attendance Records ──────────────────────────────────────────────────
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("clock_in", sa.DateTime(), nullable=True),
        sa.Column("clock_out", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), server_default="present", nullable=False),
        sa.Column("hours_worked", sa.Numeric(5, 2), nullable=True),
        sa.Column("overtime_hours", sa.Numeric(5, 2), nullable=True),
        sa.Column("late_minutes", sa.Integer(), nullable=True),
        sa.Column("early_departure_minutes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "date", name="uq_attendance_employee_date"),
    )

    # ── Performance Reviews ─────────────────────────────────────────────────
    op.create_table(
        "performance_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("review_period", sa.String(50), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("overall_rating", sa.Integer(), nullable=True),
        sa.Column("productivity_rating", sa.Integer(), nullable=True),
        sa.Column("quality_rating", sa.Integer(), nullable=True),
        sa.Column("teamwork_rating", sa.Integer(), nullable=True),
        sa.Column("communication_rating", sa.Integer(), nullable=True),
        sa.Column("leadership_rating", sa.Integer(), nullable=True),
        sa.Column("achievements", sa.Text(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("areas_for_improvement", sa.Text(), nullable=True),
        sa.Column("goals_next_period", sa.Text(), nullable=True),
        sa.Column("reviewer_comments", sa.Text(), nullable=True),
        sa.Column("employee_comments", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("is_acknowledged", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Performance Goals ───────────────────────────────────────────────────
    op.create_table(
        "performance_goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("review_id", sa.Uuid(), sa.ForeignKey("performance_reviews.id"), nullable=False),
        sa.Column("employee_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), server_default="not_started", nullable=False),
        sa.Column("progress_percent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("performance_goals")
    op.drop_table("performance_reviews")
    op.drop_table("attendance_records")
    op.drop_table("leave_requests")
    op.drop_table("leave_balances")
    op.drop_table("leave_types")
    op.drop_table("employee_documents")

    op.drop_column("employees", "manager_id")
    op.drop_column("employees", "hourly_rate")
    op.drop_column("employees", "contract_end_date")
    op.drop_column("employees", "probation_end_date")
    op.drop_column("employees", "bank_name")
    op.drop_column("employees", "bank_account_number")
    op.drop_column("employees", "emergency_contact_phone")
    op.drop_column("employees", "emergency_contact_name")
    op.drop_column("employees", "birth_date")
    op.drop_column("employees", "gender")

    op.drop_column("departments", "budget")
    op.drop_column("departments", "head_count")
    op.drop_column("departments", "description")

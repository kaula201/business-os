"""Odoo-depth payroll: salary structures, salary rules, rule parameters, work entries."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SalaryStructure(Base):
    """Salary structure — a named set of rules (Odoo salary.structure).

    e.g. "სტანდარტული თვიური", "ნახევარ განაკვეთი", "კონტრაქტორი".
    """

    __tablename__ = "salary_structures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class SalaryRule(Base):
    """Salary rule — one computation step with a formula (Odoo salary.rule).

    formula is a Python expression evaluated with a safe namespace:
      gross, base_salary, additions, deductions, pension_participant,
      worked_days, worked_hours, period_year, period_month, params (dict)
    amount_type: fixed | percentage | formula
    """

    __tablename__ = "salary_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    structure_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("salary_structures.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="addition", nullable=False)  # addition|deduction|tax|pension|net
    amount_type: Mapped[str] = mapped_column(String(20), default="fixed", nullable=False)  # fixed|percentage|formula
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)       # fixed value or percentage
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)                        # python expr for amount_type=formula
    basis: Mapped[str] = mapped_column(String(30), default="gross", nullable=False)         # gross|base|net|worked
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class RuleParameter(Base):
    """Rule parameter — configurable constant used inside formulas (Odoo rule.parameter).

    e.g. income_tax_rate=0.15, pension_employee_rate=0.02, pension_ceiling=200000.
    """

    __tablename__ = "rule_parameters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class WorkEntry(Base):
    """Work entry — attendance-derived worked time for a period (Odoo work.entry).

    Generated from attendance records; drives prorated salary rules.
    """

    __tablename__ = "work_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    period_year: Mapped[int] = mapped_column(nullable=False)
    period_month: Mapped[int] = mapped_column(nullable=False)
    worked_days: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    worked_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0, nullable=False)
    overtime_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="attendance", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class PayrollLine(Base):
    """Computed line of a payroll entry — one salary rule result (Odoo payslip.line)."""

    __tablename__ = "payroll_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    payroll_entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payroll_entries.id"), nullable=False, index=True)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("salary_rules.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="addition", nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    basis_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    formula_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class PayrollAdjustment(Base):
    """One-off bonus or deduction attached to an employee for a period (Odoo payslip.input).

    e.g. ბონუსი 500 ₾, პრემია, დაჯარიმება, ავანსი. Auto-included in rule-based
    calculation for the matching period.
    """

    __tablename__ = "payroll_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    period_year: Mapped[int] = mapped_column(nullable=False)
    period_month: Mapped[int] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default="bonus", nullable=False)  # bonus|premium|fine|advance|other
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

"""Adopt the pre-Alembic schema as a safe baseline.

Revision ID: 001_initial
Revises:
Create Date: 2026-06-24

This project originally created its schema from SQLAlchemy metadata at startup.
`app.core.migrate_schema` creates/adopts that schema once and stamps this
revision without executing destructive DDL. All schema changes after this
baseline must be implemented as additive Alembic revisions.
"""
from typing import Sequence, Union

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Baseline marker: the migration runner adopts the existing schema."""


def downgrade() -> None:
    """A baseline downgrade intentionally leaves business data untouched."""

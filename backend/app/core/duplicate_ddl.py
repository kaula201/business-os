"""Helpers for running Alembic against a schema create_all already built.

ConfigParser treats ``%`` as interpolation, so a password that contains
``%`` must be stored as ``%%`` and is restored when the URL is read back.

A fresh production database is created from current ORM metadata and then
replayed through every Alembic revision (the 001 baseline does not emit
DDL). Revisions that add columns or tables the models already include raise
duplicate-object errors; those are safe to skip. Any other error still fails
the migration.
"""
from __future__ import annotations

_INSTALLED = False
# duplicate_column, duplicate_table, duplicate_object
_DUPLICATE_SQLSTATES = frozenset({"42701", "42P07", "42710"})


def escape_alembic_config_value(value: str) -> str:
    """Escape ``%`` so Alembic's ConfigParser keeps a literal percent."""
    return value.replace("%", "%%")


def _sqlstate(exc: BaseException) -> str | None:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for attr in ("pgcode", "sqlstate"):
            code = getattr(current, attr, None)
            if code:
                return str(code)
        current = getattr(current, "orig", None) or current.__cause__
    return None


def install_duplicate_ddl_guard() -> None:
    """Skip Alembic ops that only fail because the object already exists."""
    global _INSTALLED
    if _INSTALLED:
        return

    from alembic.operations import Operations

    original = Operations.invoke

    def invoke(self, operation):  # type: ignore[no-untyped-def]
        bind = self.get_bind()
        nested = bind.begin_nested()
        try:
            result = original(self, operation)
        except Exception as exc:
            nested.rollback()
            if _sqlstate(exc) in _DUPLICATE_SQLSTATES:
                return None
            raise
        else:
            nested.commit()
            return result

    Operations.invoke = invoke  # type: ignore[method-assign]
    _INSTALLED = True

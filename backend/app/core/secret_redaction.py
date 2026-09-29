"""Hide database passwords in migration errors and log records."""
from __future__ import annotations

import logging
from urllib.parse import quote

from sqlalchemy.engine.url import make_url


def redact_url(url: str) -> str:
    """Render a SQLAlchemy URL with the password replaced."""
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "postgresql://***"


def _secrets(url: str) -> list[str]:
    try:
        password = make_url(url).password or ""
    except Exception:
        return []
    if not password:
        return []
    encoded = quote(password, safe="")
    values = [password]
    if encoded and encoded != password:
        values.append(encoded)
    return values


def scrub(text: str, url: str) -> str:
    cleaned = text
    for secret in _secrets(url):
        cleaned = cleaned.replace(secret, "***")
    return cleaned


def _exception_blob(exc: BaseException, seen: set[int] | None = None) -> str:
    seen = seen if seen is not None else set()
    if id(exc) in seen:
        return ""
    seen.add(id(exc))
    parts = [str(exc), repr(exc)]
    for attr in ("statement", "detail"):
        value = getattr(exc, attr, None)
        if value:
            parts.append(str(value))
    orig = getattr(exc, "orig", None)
    if isinstance(orig, BaseException):
        parts.append(_exception_blob(orig, seen))
    if exc.__cause__ is not None:
        parts.append(_exception_blob(exc.__cause__, seen))
    return "\n".join(parts)


def hides_password(exc: BaseException, url: str) -> bool:
    blob = _exception_blob(exc)
    return any(secret in blob for secret in _secrets(url))


def public_migration_error(exc: BaseException, url: str) -> RuntimeError:
    """Error safe to print: redacted URL, password stripped, no chained SQL."""
    detail = scrub(str(exc), url)
    return RuntimeError(f"Migration failed for {redact_url(url)}: {detail}")


class PasswordRedactFilter(logging.Filter):
    """Replace a URL password if a log record contains it."""

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._scrub_value(record.msg)
        if isinstance(record.args, dict):
            record.args = {key: self._scrub_value(value) for key, value in record.args.items()}
        elif isinstance(record.args, tuple):
            record.args = tuple(self._scrub_value(value) for value in record.args)
        return True

    def _scrub_value(self, value: object) -> object:
        if isinstance(value, str):
            return scrub(value, self._url)
        return value


def install_log_redaction(url: str) -> PasswordRedactFilter:
    redactor = PasswordRedactFilter(url)
    logging.getLogger().addFilter(redactor)
    return redactor

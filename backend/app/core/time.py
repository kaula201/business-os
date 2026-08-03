"""UTC time helpers compatible with the existing timezone-naive DB columns."""
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current UTC as a naive datetime for PostgreSQL TIMESTAMP columns."""
    return datetime.now(UTC).replace(tzinfo=None)

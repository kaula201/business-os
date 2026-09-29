"""Keep Alembic's version column wide enough for this project's revision ids.

Alembic creates ``alembic_version.version_num`` as ``VARCHAR(32)``.
``122_pos_restaurant_courses_floorplan`` and three other revision ids are
longer than that, so ``upgrade`` fails while recording revision 122 on any
database whose version table is still the default width. Revision ids are
not renamed.

Call this before ``stamp`` or ``upgrade``. It is safe to repeat: a missing
table is created at ``VARCHAR(255)`` (so Alembic does not recreate
``VARCHAR(32)``), and an existing short column is widened in place.
"""
from __future__ import annotations

from sqlalchemy import text

_CREATE = """
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(255) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
)
"""
_LENGTH = """
SELECT character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'alembic_version'
  AND column_name = 'version_num'
"""
_WIDEN = "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"


def ensure_alembic_version_width(connection) -> None:
    """Widen ``version_num`` on a sync connection. Caller commits."""
    exists = connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
    if not exists:
        connection.execute(text(_CREATE))
        return
    length = connection.execute(text(_LENGTH)).scalar()
    if length is None or int(length) < 255:
        connection.execute(text(_WIDEN))

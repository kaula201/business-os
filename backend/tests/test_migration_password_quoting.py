"""Password quoting for prod migrations. No database required."""
import importlib.util
from pathlib import Path

from alembic.config import Config

from app.core.duplicate_ddl import escape_alembic_config_value


def _load_063():
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "063_rls_app_role.py"
    spec = importlib.util.spec_from_file_location("migration_063_quote", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_dollar_quote_does_not_close_early_when_password_ends_with_tag():
    quote = _load_063()._dollar_quote
    assert quote("secret$pw") == "$pwx$secret$pw$pwx$"
    assert quote("a$pw$b") == "$pwx$a$pw$b$pwx$"


def test_dollar_quote_plain_password_uses_the_short_tag():
    quote = _load_063()._dollar_quote
    assert quote("app-secret-value") == "$pw$app-secret-value$pw$"


def test_alembic_config_roundtrips_percent_in_password():
    url = "postgresql+psycopg2://business_os:100%ok@postgres:5432/business_os"
    cfg = Config()
    cfg.set_main_option("sqlalchemy.url", escape_alembic_config_value(url))
    assert cfg.get_main_option("sqlalchemy.url") == url

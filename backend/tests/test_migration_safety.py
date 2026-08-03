from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
PROJECT = BACKEND.parent


def upgrade_body(source: str) -> str:
    return source.split("def upgrade()", 1)[1].split("def downgrade()", 1)[0].lower()


def test_alembic_runtime_and_upgrades_contain_no_destructive_ddl():
    env_source = (BACKEND / "migrations" / "env.py").read_text()
    assert "drop type" not in env_source.lower()
    assert "cascade" not in env_source.lower()
    assert "import app.models" in env_source

    for migration in (BACKEND / "migrations" / "versions").glob("*.py"):
        source = migration.read_text()
        upgrade = upgrade_body(source)
        assert "drop type" not in upgrade, migration.name
        assert " cascade" not in upgrade, migration.name
        assert "op.drop_table" not in upgrade, migration.name
        assert "op.drop_column" not in upgrade, migration.name


def test_startup_adopts_baseline_then_uses_alembic_upgrade():
    migration_runner = BACKEND / "app" / "core" / "migrate_schema.py"
    assert migration_runner.exists()
    source = migration_runner.read_text()
    assert "command.stamp" in source
    assert "command.upgrade" in source
    assert "init_db" in source

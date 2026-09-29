"""Fresh-database bootstrap: long revision ids and the module catalog."""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _revision_ids() -> list[str]:
    ids: list[str] = []
    for path in (BACKEND / "migrations" / "versions").glob("*.py"):
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("revision") and "=" in stripped and "down_revision" not in stripped:
                value = stripped.split("=", 1)[1].strip().strip(",").strip("'\"")
                if value and not value.startswith("Union"):
                    ids.append(value)
                break
    return ids


def test_long_revision_ids_stay_as_they_are():
    long_ids = [revision for revision in _revision_ids() if len(revision) > 32]
    assert "122_pos_restaurant_courses_floorplan" in long_ids
    assert len(long_ids) >= 4
    assert all(not revision.startswith("122_pos_restaurant") or revision.endswith("floorplan") for revision in long_ids)


def test_upgrade_widens_version_num_before_migrations():
    env_source = (BACKEND / "migrations" / "env.py").read_text()
    assert "ensure_alembic_version_width" in env_source
    widen_at = env_source.index("ensure_alembic_version_width")
    run_at = env_source.index("context.run_migrations()")
    assert widen_at < run_at


def test_catalog_seed_does_not_wipe_existing_rows():
    source = (BACKEND / "seed_modules.py").read_text()
    assert "DELETE FROM app_modules" not in source
    assert "DELETE FROM company_modules" not in source
    assert "DELETE FROM module_permissions" not in source


def test_prod_bootstrap_does_not_call_demo_seed():
    migrate = (BACKEND / "app" / "core" / "migrate_schema.py").read_text()
    main = (BACKEND / "app" / "main.py").read_text()
    compose = (BACKEND.parent / "docker-compose.prod.yml").read_text()
    assert "from seed import" not in migrate
    assert "import seed\n" not in migrate
    assert "seed.seed" not in migrate
    assert "seed.py" not in compose
    assert "admin@demo.ge" not in migrate
    assert "seed_modules" in main
    assert "from seed import seed" not in main


def test_bootstrap_reapplies_tenant_rls_after_upgrade():
    source = (BACKEND / "app" / "core" / "migrate_schema.py").read_text()
    assert "FORCE ROW LEVEL SECURITY" in source
    call = source.split("def main()", 1)[1]
    assert call.index("command.upgrade") < call.index("_ensure_tenant_rls")


def test_helpdesk_is_in_the_module_catalog():
    source = (BACKEND / "seed_modules.py").read_text()
    catalog, _, after = source.partition("OPERATIONAL_MODULES")
    assert '"helpdesk"' in catalog
    assert '"helpdesk"' in after.split("def permission_flags", 1)[0]

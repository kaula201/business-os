"""Rename require_module codes to catalog codes and add new catalog codes (#52).

Revision ID: 157_module_code_renames
Revises: 155_backfill_base_company_modules
Create Date: 2026-10-12

Require_module codes were renamed to catalog codes:

    warehouse      -> wms
    quality-control -> quality
    leaves          -> hr
    recruitment     -> hr
    live-chat       -> helpdesk

New catalog codes added in this migration:

    ecommerce, contracts, approvals

The mapping preserves enabled flags using AND semantics: a target module is
enabled only if all source rows that map to it are enabled AND the target row
(if it already existed) was enabled. Old company_modules rows are kept for
downgrade; old app_modules are deactivated after mapping.

RLS stays fail-closed: each company is pinned with a transaction-local
``app.current_company_id``. A backup table records the original target state
so downgrade can restore it exactly. Idempotent.
"""

import logging

from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "157_module_code_renames"
down_revision = "155_backfill_base_company_modules"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

RENAMES = (
    ("warehouse", "wms"),
    ("quality-control", "quality"),
    ("leaves", "hr"),
    ("recruitment", "hr"),
    ("live-chat", "helpdesk"),
)

NEW_CODES = (
    ("ecommerce", "ელ. კომერცია", "Online store, cart, checkout", "Store", "/ecommerce", "sales", 300),
    ("contracts", "ხელშეკრულებები", "Contracts", "FileText", "/contracts", "sales", 301),
    ("approvals", "დამტკიცებები", "Approval requests", "BadgeCheck", "/approvals", "operations", 302),
)

BACKUP_TABLE = "mig157_company_module_backup"

# Fail-closed tenant policy: with no pinned company nothing is visible.
POLICY = "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"


def ensure_backup_table(bind: Connection) -> None:
    """Create the backup table and its RLS policy if they do not exist."""
    bind.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} (
                company_id uuid NOT NULL,
                target_code varchar(50) NOT NULL,
                target_existed boolean NOT NULL,
                target_prev_enabled boolean NULL,
                PRIMARY KEY (company_id, target_code)
            )
            """
        )
    )
    bind.execute(text(f"ALTER TABLE {BACKUP_TABLE} ENABLE ROW LEVEL SECURITY"))
    bind.execute(text(f"ALTER TABLE {BACKUP_TABLE} FORCE ROW LEVEL SECURITY"))

    policy_exists = bind.execute(
        text(
            """
            SELECT 1
            FROM pg_policies
            WHERE schemaname = current_schema()
              AND tablename = :table_name
              AND policyname = 'tenant_isolation'
            """
        ),
        {"table_name": BACKUP_TABLE},
    ).fetchone()

    if policy_exists is None:
        bind.execute(
            text(
                f"CREATE POLICY tenant_isolation ON {BACKUP_TABLE} "
                f"USING ({POLICY}) WITH CHECK ({POLICY})"
            )
        )


def insert_new_catalog_codes(bind: Connection) -> int:
    """
    Insert new catalog modules.

    Company-module rows are intentionally **not** inserted for these new
    modules; they will only become available when explicitly enabled later.
    """
    inserted_total = 0
    for code, name, description, icon, route, category, sort_order in NEW_CODES:
        result = bind.execute(
            text(
                """
                INSERT INTO app_modules
                    (id, code, name, description, icon, route, category, is_active, sort_order)
                VALUES
                    (gen_random_uuid(), :code, :name, :description, :icon, :route, :category, true, :sort_order)
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "code": code,
                "name": name,
                "description": description,
                "icon": icon,
                "route": route,
                "category": category,
                "sort_order": sort_order,
            },
        )
        inserted_total += result.rowcount or 0
    return inserted_total


def map_renamed_codes(bind: Connection) -> dict:
    """
    Map old require_module codes to target catalog codes.

    Returns counts:
        companies_touched, targets_created, targets_updated, old_rows_seen
    """
    old_codes = [old for old, _ in RENAMES]
    old_modules = bind.execute(
        text("SELECT code, id FROM app_modules WHERE code = ANY(:codes)"),
        {"codes": old_codes},
    ).fetchall()

    if not old_modules:
        return {"companies_touched": 0, "targets_created": 0, "targets_updated": 0, "old_rows_seen": 0}

    target_codes = list({new for _, new in RENAMES})
    target_modules = bind.execute(
        text("SELECT code, id FROM app_modules WHERE code = ANY(:codes)"),
        {"codes": target_codes},
    ).fetchall()

    target_id_by_code = {row.code: row.id for row in target_modules}
    missing_targets = [code for code in target_codes if code not in target_id_by_code]
    for missing in missing_targets:
        logger.warning(
            "157_module_code_renames: target module %s missing; skipping mapping for it",
            missing,
        )

    # Only keep mappings whose target module exists.
    old_to_target = {old: new for old, new in RENAMES if new in target_id_by_code}
    target_old_codes = {}
    for old, new in old_to_target.items():
        target_old_codes.setdefault(new, []).append(old)

    counts = {
        "companies_touched": 0,
        "targets_created": 0,
        "targets_updated": 0,
        "old_rows_seen": 0,
    }

    company_ids = bind.execute(text("SELECT id::text FROM companies")).scalars().all()

    for cid in company_ids:
        bind.execute(text("SELECT set_config('app.current_company_id', :cid, true)"), {"cid": cid})
        company_touched = False

        for target_code, old_codes_for_target in target_old_codes.items():
            rows = bind.execute(
                text(
                    """
                    SELECT cm.enabled
                    FROM company_modules cm
                    JOIN app_modules am ON am.id = cm.module_id
                    WHERE cm.company_id = CAST(:cid AS uuid)
                      AND am.code = ANY(:old_codes)
                    """
                ),
                {"cid": cid, "old_codes": old_codes_for_target},
            ).fetchall()

            if not rows:
                continue

            old_flags = [r[0] for r in rows]
            counts["old_rows_seen"] += len(old_flags)

            target_id = target_id_by_code[target_code]

            existing = bind.execute(
                text(
                    """
                    SELECT enabled
                    FROM company_modules
                    WHERE company_id = CAST(:cid AS uuid)
                      AND module_id = :target_id
                    """
                ),
                {"cid": cid, "target_id": target_id},
            ).fetchone()

            target_existed = existing is not None
            target_prev_enabled = existing[0] if existing is not None else None

            # Backup row is written once; subsequent runs keep the original state.
            bind.execute(
                text(
                    f"""
                    INSERT INTO {BACKUP_TABLE}
                        (company_id, target_code, target_existed, target_prev_enabled)
                    VALUES
                        (CAST(:cid AS uuid), :target_code, :target_existed, :target_prev_enabled)
                    ON CONFLICT (company_id, target_code) DO NOTHING
                    """
                ),
                {
                    "cid": cid,
                    "target_code": target_code,
                    "target_existed": target_existed,
                    "target_prev_enabled": target_prev_enabled,
                },
            )

            backup_row = bind.execute(
                text(
                    f"""
                    SELECT target_existed, target_prev_enabled
                    FROM {BACKUP_TABLE}
                    WHERE company_id = CAST(:cid AS uuid)
                      AND target_code = :target_code
                    """
                ),
                {"cid": cid, "target_code": target_code},
            ).fetchone()

            backup_existed, backup_prev_enabled = backup_row[0], backup_row[1]

            # AND semantics: all old flags must be true AND the original target
            # (if it existed) must have been true.
            result = all(old_flags)
            if backup_existed:
                result = result and backup_prev_enabled

            if target_existed:
                bind.execute(
                    text(
                        """
                        UPDATE company_modules
                        SET enabled = :result,
                            updated_at = now()
                        WHERE company_id = CAST(:cid AS uuid)
                          AND module_id = :target_id
                        """
                    ),
                    {"cid": cid, "target_id": target_id, "result": result},
                )
                counts["targets_updated"] += 1
            else:
                bind.execute(
                    text(
                        """
                        INSERT INTO company_modules (id, company_id, module_id, enabled)
                        VALUES (gen_random_uuid(), CAST(:cid AS uuid), :target_id, :result)
                        """
                    ),
                    {"cid": cid, "target_id": target_id, "result": result},
                )
                counts["targets_created"] += 1

            company_touched = True

        if company_touched:
            counts["companies_touched"] += 1

    # Old company_modules rows are left untouched for downgrade.
    bind.execute(
        text("UPDATE app_modules SET is_active = false WHERE code = ANY(:codes)"),
        {"codes": old_codes},
    )

    bind.execute(text("SELECT set_config('app.current_company_id', '', true)"))

    return counts


def restore_renamed_codes(bind: Connection) -> None:
    """
    Restore target rows to their pre-migration state using the backup table,
    then reactivate the old app_modules.
    """
    company_ids = bind.execute(text("SELECT id::text FROM companies")).scalars().all()

    for cid in company_ids:
        bind.execute(text("SELECT set_config('app.current_company_id', :cid, true)"), {"cid": cid})

        backup_rows = bind.execute(
            text(
                f"""
                SELECT target_code, target_existed, target_prev_enabled
                FROM {BACKUP_TABLE}
                WHERE company_id = CAST(:cid AS uuid)
                """
            ),
            {"cid": cid},
        ).fetchall()

        for target_code, existed, prev_enabled in backup_rows:
            module = bind.execute(
                text("SELECT id FROM app_modules WHERE code = :code"),
                {"code": target_code},
            ).fetchone()
            if module is None:
                continue

            target_id = module[0]

            if existed:
                bind.execute(
                    text(
                        """
                        UPDATE company_modules
                        SET enabled = :prev_enabled,
                            updated_at = now()
                        WHERE company_id = CAST(:cid AS uuid)
                          AND module_id = :target_id
                        """
                    ),
                    {"cid": cid, "target_id": target_id, "prev_enabled": prev_enabled},
                )
            else:
                bind.execute(
                    text(
                        """
                        DELETE FROM company_modules
                        WHERE company_id = CAST(:cid AS uuid)
                          AND module_id = :target_id
                        """
                    ),
                    {"cid": cid, "target_id": target_id},
                )

    bind.execute(
        text("UPDATE app_modules SET is_active = true WHERE code = ANY(:codes)"),
        {"codes": [old for old, _ in RENAMES]},
    )

    bind.execute(text("SELECT set_config('app.current_company_id', '', true)"))


def remove_new_catalog_codes(bind: Connection) -> None:
    """
    Remove the new catalog modules if no company_modules row references them.

    company_modules is tenant-scoped (RLS), so references are checked per
    pinned company.
    """
    company_ids = bind.execute(text("SELECT id::text FROM companies")).scalars().all()

    for code, *_ in NEW_CODES:
        module = bind.execute(
            text("SELECT id FROM app_modules WHERE code = :code"),
            {"code": code},
        ).fetchone()
        if module is None:
            continue

        mid = module[0]
        has_ref = False
        for cid in company_ids:
            bind.execute(text("SELECT set_config('app.current_company_id', :cid, true)"), {"cid": cid})
            if bind.execute(
                text("SELECT EXISTS(SELECT 1 FROM company_modules WHERE module_id = :mid)"),
                {"mid": mid},
            ).scalar():
                has_ref = True
                break
        bind.execute(text("SELECT set_config('app.current_company_id', '', true)"))

        if has_ref:
            continue

        bind.execute(text("DELETE FROM module_permissions WHERE module_id = :mid"), {"mid": mid})
        bind.execute(text("DELETE FROM app_modules WHERE id = :mid"), {"mid": mid})


def upgrade():
    bind = op.get_bind()
    ensure_backup_table(bind)
    inserted_new = insert_new_catalog_codes(bind)
    counts = map_renamed_codes(bind)
    logger.info(
        "157_module_code_renames: inserted_new=%s counts=%s",
        inserted_new,
        counts,
    )


def downgrade():
    bind = op.get_bind()
    restore_renamed_codes(bind)
    remove_new_catalog_codes(bind)
    bind.execute(text(f"DROP TABLE IF EXISTS {BACKUP_TABLE}"))

"""Unify product stock with warehouse inventory balances.

Revision ID: 061_inventory_stock_consistency
Revises: 060_materialized_views
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "061_inventory_stock_consistency"
down_revision: Union[str, None] = "060_materialized_views"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ProductCategory.is_active existed in the ORM without a matching migration.
    op.execute(
        "ALTER TABLE categories "
        "ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"
    )

    # Legacy products could carry current_stock without any warehouse. Ensure
    # those companies have a usable default warehouse before migrating balances.
    op.execute(
        """
        INSERT INTO warehouses (
            id, company_id, code, name, is_default, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), orphan.company_id,
            CASE WHEN NOT EXISTS (
                SELECT 1 FROM warehouses w2
                WHERE w2.company_id = orphan.company_id AND w2.code = 'MAIN'
            ) THEN 'MAIN' ELSE 'LEGACY-WH' END,
            'მთავარი საწყობი',
            TRUE, TRUE, NOW(), NOW()
        FROM (
            SELECT DISTINCT p.company_id
            FROM products p
            WHERE p.current_stock > 0
              AND NOT EXISTS (
                  SELECT 1 FROM inventory_balances ib
                  WHERE ib.company_id = p.company_id
                    AND ib.product_id = p.id
              )
        ) AS orphan
        WHERE NOT EXISTS (
            SELECT 1 FROM warehouses w
            WHERE w.company_id = orphan.company_id AND w.is_active = TRUE
        )
        """
    )
    op.execute(
        """
        WITH missing_default AS (
            SELECT DISTINCT p.company_id
            FROM products p
            WHERE p.current_stock > 0
              AND NOT EXISTS (
                  SELECT 1 FROM inventory_balances ib
                  WHERE ib.company_id = p.company_id
                    AND ib.product_id = p.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM warehouses w
                  WHERE w.company_id = p.company_id
                    AND w.is_active = TRUE
                    AND w.is_default = TRUE
              )
        ), selected AS (
            SELECT DISTINCT ON (w.company_id) w.id
            FROM warehouses w
            JOIN missing_default md ON md.company_id = w.company_id
            WHERE w.is_active = TRUE
            ORDER BY w.company_id, w.created_at, w.id
        )
        UPDATE warehouses w
        SET is_default = TRUE, updated_at = NOW()
        FROM selected s
        WHERE w.id = s.id
        """
    )

    # Preserve every positive legacy stock value as a warehouse balance and
    # record an auditable reconciliation movement.
    op.execute(
        """
        WITH inserted AS (
            INSERT INTO inventory_balances (
                id, company_id, warehouse_id, product_id,
                quantity, reserved_quantity, updated_at
            )
            SELECT
                gen_random_uuid(), p.company_id, w.id, p.id,
                p.current_stock, 0, NOW()
            FROM products p
            JOIN (
                SELECT DISTINCT ON (company_id) id, company_id
                FROM warehouses
                WHERE is_default = TRUE AND is_active = TRUE
                ORDER BY company_id, created_at, id
            ) w ON w.company_id = p.company_id
            WHERE p.current_stock > 0
              AND NOT EXISTS (
                  SELECT 1 FROM inventory_balances ib
                  WHERE ib.company_id = p.company_id
                    AND ib.product_id = p.id
              )
            RETURNING company_id, warehouse_id, product_id, quantity
        )
        INSERT INTO inventory_movements (
            id, company_id, warehouse_id, product_id, movement_type,
            quantity, balance_before, balance_after,
            reserved_before, reserved_after, reason, reason_category,
            notes, reference, reference_type, created_at
        )
        SELECT
            gen_random_uuid(), company_id, warehouse_id, product_id, 'adjustment',
            quantity, 0, quantity, 0, 0, 'legacy_reconciliation', 'adjustment',
            'Legacy products.current_stock migrated to warehouse balance',
            'MIGRATION-061', 'migration', NOW()
        FROM inserted
        """
    )

    # inventory_balances is canonical; products.current_stock remains a
    # denormalized aggregate for existing list/report compatibility.
    op.execute(
        """
        UPDATE products p
        SET current_stock = COALESCE((
            SELECT SUM(ib.quantity)
            FROM inventory_balances ib
            WHERE ib.company_id = p.company_id
              AND ib.product_id = p.id
        ), 0),
        updated_at = NOW()
        """
    )


def downgrade() -> None:
    # Reconciliation data is intentionally retained to avoid stock data loss.
    op.execute("ALTER TABLE categories DROP COLUMN IF EXISTS is_active")

"""issue #25, REQ-PKG/AC-PKG

Modules are sold standalone so catalog depends_on must not cross v3.0 bundles.
depends_on is informational (no runtime reader).
"""

from alembic import op
from sqlalchemy import text

revision = "156_catalog_depends_on_bundles"
down_revision = "155_backfill_base_company_modules"
branch_labels = None
depends_on = None

# (code, depends_on) pairs that must be cleared if they still point to the old bundle dependency
EDGES = (
    ("maintenance", "production"),
    ("supplier-finance", "suppliers"),
    ("customer-finance", "invoices"),
    ("production", "inventory"),
)


def upgrade():
    for code, dep in EDGES:
        op.get_bind().execute(
            text(
                "UPDATE app_modules SET depends_on = NULL "
                "WHERE code = :code AND depends_on = :dep"
            ),
            {"code": code, "dep": dep},
        )


def downgrade():
    for code, dep in EDGES:
        op.get_bind().execute(
            text(
                "UPDATE app_modules SET depends_on = :dep "
                "WHERE code = :code AND depends_on IS NULL"
            ),
            {"code": code, "dep": dep},
        )

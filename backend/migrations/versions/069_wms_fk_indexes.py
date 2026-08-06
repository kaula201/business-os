"""WMS foreign-key indexes for lookup and join paths.

Revision ID: 069_wms_fk_indexes
Revises: 068_rag_defaults_tenant_rls
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op

revision: str = "069_wms_fk_indexes"
down_revision: Union[str, None] = "068_rag_defaults_tenant_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_product_batches_warehouse_id",
        "product_batches",
        ["warehouse_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_product_serials_batch_id",
        "product_serials",
        ["batch_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_product_serials_warehouse_id",
        "product_serials",
        ["warehouse_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_product_serials_warehouse_id", table_name="product_serials")
    op.drop_index("ix_product_serials_batch_id", table_name="product_serials")
    op.drop_index("ix_product_batches_warehouse_id", table_name="product_batches")

"""RAG defaults/index and tenant RLS for post-064 tables.

Revision ID: 068_rag_defaults_tenant_rls
Revises: 067_rag_embeddings
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "068_rag_defaults_tenant_rls"
down_revision: Union[str, None] = "067_rag_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("product_batches", "product_serials", "embeddings")


def upgrade() -> None:
    # Fix the already-deployed 067 table and pin the OpenAI embedding dimension.
    op.execute("ALTER TABLE embeddings ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    op.execute(
        "ALTER TABLE embeddings ALTER COLUMN embedding "
        "TYPE vector(1536) USING embedding::vector(1536)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_embeddings_vector_cosine "
        "ON embeddings USING hnsw (embedding vector_cosine_ops)"
    )

    predicate = (
        "current_setting('app.current_company_id', true) IS NULL "
        "OR current_setting('app.current_company_id', true) = '' "
        "OR company_id::text = current_setting('app.current_company_id', true)"
    )
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" '
            f'USING ({predicate}) WITH CHECK ({predicate})'
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    op.execute("DROP INDEX IF EXISTS ix_embeddings_vector_cosine")
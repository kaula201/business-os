"""RAG: embeddings table with pgvector support.

Revision ID: 067_rag_embeddings
Revises: 066_wms_batches_serials
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "067_rag_embeddings"
down_revision: Union[str, None] = "066_wms_batches_serials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Migration 009 already creates this table on a fresh chain.  Some deployed
    # databases predate that effective DDL, so keep this migration idempotent and
    # repair only missing objects instead of recreating the table.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies(id),
            content_type varchar(50) NOT NULL,
            content_id uuid NOT NULL,
            content_text text NOT NULL,
            embedding vector(1536),
            created_at timestamp NOT NULL DEFAULT now(),
            updated_at timestamp NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "ALTER TABLE embeddings "
        "ADD COLUMN IF NOT EXISTS embedding vector(1536)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_embeddings_company_id "
        "ON embeddings (company_id)"
    )


def downgrade() -> None:
    # The table and its vector column belong to migration 009.
    op.execute("DROP INDEX IF EXISTS ix_embeddings_company_id")

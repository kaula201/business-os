"""Add pgvector extension and embeddings table for RAG.

Revision ID: 009_pgvector_rag
Revises: 008_email_verification
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_pgvector_rag"
down_revision: Union[str, None] = "008_email_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "embeddings",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("content_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "content_type", "content_id", name="uq_embedding_content"),
    )
    op.create_index("ix_embeddings_company_type", "embeddings", ["company_id", "content_type"])
    # Add vector column via raw SQL (pgvector type)
    op.execute("ALTER TABLE embeddings ADD COLUMN embedding vector(1536)")
    op.execute("CREATE INDEX ix_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")


def downgrade() -> None:
    op.drop_table("embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")

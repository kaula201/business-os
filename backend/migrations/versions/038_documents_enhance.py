"""Enhance documents: folder hierarchy, approval, retention, preview, security.

Revision ID: 038_documents_enhance
Revises: 037_supplier_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "038_documents_enhance"
down_revision: Union[str, None] = "037_supplier_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DocumentCategory enhancements (parent_id already exists from 024)
    op.add_column("document_categories", sa.Column("path", sa.String(1000), nullable=True))
    op.add_column("document_categories", sa.Column("level", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("document_categories", sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("document_categories", sa.Column("allowed_extensions", sa.Text(), nullable=True))
    op.add_column("document_categories", sa.Column("max_file_size", sa.Integer(), nullable=True))
    op.add_column("document_categories", sa.Column("retention_days", sa.Integer(), nullable=True))
    op.add_column("document_categories", sa.Column("retention_policy", sa.String(20), server_default="indefinite", nullable=False))
    op.add_column("document_categories", sa.Column("access_roles", sa.Text(), nullable=True))

    # Document enhancements
    op.add_column("documents", sa.Column("has_preview", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("documents", sa.Column("preview_path", sa.String(1000), nullable=True))
    op.add_column("documents", sa.Column("thumbnail_path", sa.String(1000), nullable=True))
    op.add_column("documents", sa.Column("approval_status", sa.String(20), server_default="draft", nullable=False))
    op.add_column("documents", sa.Column("approved_by", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_doc_approved_by", "documents", "users", ["approved_by"], ["id"])
    op.add_column("documents", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("documents", sa.Column("approval_notes", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("submitted_for_approval_at", sa.DateTime(), nullable=True))
    op.add_column("documents", sa.Column("retention_days", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("expires_at", sa.DateTime(), nullable=True))

    # DocumentVersion enhancements
    op.add_column("document_versions", sa.Column("checksum", sa.String(64), nullable=True))
    op.add_column("document_versions", sa.Column("change_summary", sa.Text(), nullable=True))
    op.add_column("document_versions", sa.Column("is_current", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    # New DocumentApproval table
    op.create_table(
        "document_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_by", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"],),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"],),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"],),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_approvals_doc", "document_approvals", ["document_id"])
    op.create_index("ix_document_approvals_company", "document_approvals", ["company_id"])


def downgrade() -> None:
    op.drop_table("document_approvals")
    op.drop_column("document_versions", "is_current")
    op.drop_column("document_versions", "change_summary")
    op.drop_column("document_versions", "checksum")
    op.drop_column("documents", "expires_at")
    op.drop_column("documents", "retention_days")
    op.drop_column("documents", "submitted_for_approval_at")
    op.drop_column("documents", "approval_notes")
    op.drop_column("documents", "approved_at")
    op.drop_constraint("fk_doc_approved_by", "documents", type_="foreignkey")
    op.drop_column("documents", "approved_by")
    op.drop_column("documents", "approval_status")
    op.drop_column("documents", "thumbnail_path")
    op.drop_column("documents", "preview_path")
    op.drop_column("documents", "has_preview")
    op.drop_column("document_categories", "access_roles")
    op.drop_column("document_categories", "retention_policy")
    op.drop_column("document_categories", "retention_days")
    op.drop_column("document_categories", "max_file_size")
    op.drop_column("document_categories", "allowed_extensions")
    op.drop_column("document_categories", "sort_order")
    op.drop_column("document_categories", "level")
    op.drop_column("document_categories", "path")

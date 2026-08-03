"""Enhance clients: credit_limit, contact fields on client, duplicate protection.

Revision ID: 048_clients_enhance
Revises: 047_fleet_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "048_clients_enhance"
down_revision: Union[str, None] = "047_fleet_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Client: credit limit + contact fields
    op.add_column("clients", sa.Column("credit_limit", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False))
    op.add_column("clients", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("clients", sa.Column("email", sa.String(255), nullable=True))

    # Unique indexes for duplicate prevention (per company)
    op.create_index("uq_client_company_identification", "clients", ["company_id", "identification_code"], unique=True)
    op.create_index("uq_client_company_email", "clients", ["company_id", "email"], unique=True, postgresql_where=sa.text("email IS NOT NULL"))
    op.create_index("uq_client_company_phone", "clients", ["company_id", "phone"], unique=True, postgresql_where=sa.text("phone IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_client_company_phone", table_name="clients")
    op.drop_index("uq_client_company_email", table_name="clients")
    op.drop_index("uq_client_company_identification", table_name="clients")
    op.drop_column("clients", "email")
    op.drop_column("clients", "phone")
    op.drop_column("clients", "credit_limit")

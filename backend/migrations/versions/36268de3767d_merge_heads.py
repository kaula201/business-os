"""merge_heads

Revision ID: 36268de3767d
Revises: 041_products_enhance, 043_orders_enhance
Create Date: 2026-08-03 16:31:08.787171

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36268de3767d'
down_revision: Union[str, None] = ('041_products_enhance', '043_orders_enhance')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

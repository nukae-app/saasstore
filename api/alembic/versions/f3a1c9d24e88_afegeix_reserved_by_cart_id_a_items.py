"""afegeix reserved_by_cart_id a items

Revision ID: f3a1c9d24e88
Revises: 2c690b8e9247
Create Date: 2026-07-04 09:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a1c9d24e88'
down_revision: Union[str, None] = '2c690b8e9247'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('items', sa.Column('reserved_by_cart_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'items_reserved_by_cart_id_fkey', 'items', 'carts',
        ['reserved_by_cart_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('items_reserved_by_cart_id_fkey', 'items', type_='foreignkey')
    op.drop_column('items', 'reserved_by_cart_id')

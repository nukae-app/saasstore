"""add_condicion_item

Revision ID: 3051426b0eaf
Revises: ab4340a7ea5a
Create Date: 2026-06-11 09:30:07.117484

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '3051426b0eaf'
down_revision: Union[str, None] = 'ab4340a7ea5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

condicion_enum = sa.Enum('nou', 'segona_ma', name='condicion_item')


def upgrade() -> None:
    condicion_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'items',
        sa.Column(
            'condicion',
            condicion_enum,
            nullable=False,
            server_default='segona_ma',
        ),
    )
    op.create_index('ix_items_condicion', 'items', ['condicion'])


def downgrade() -> None:
    op.drop_index('ix_items_condicion', table_name='items')
    op.drop_column('items', 'condicion')
    condicion_enum.drop(op.get_bind(), checkfirst=True)

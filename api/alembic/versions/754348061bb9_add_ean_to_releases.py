"""add ean to releases

Revision ID: 754348061bb9
Revises: c4024b25f384
Create Date: 2026-07-14 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '754348061bb9'
down_revision: Union[str, None] = 'c4024b25f384'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('releases', sa.Column('ean', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_releases_ean'), 'releases', ['ean'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_releases_ean'), table_name='releases')
    op.drop_column('releases', 'ean')

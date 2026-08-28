"""afegir theme i custom_css a configuracio_botiga

Revision ID: af9e10038ae7
Revises: 14115a9c1e29
Create Date: 2026-08-28 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'af9e10038ae7'
down_revision: Union[str, None] = '14115a9c1e29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('configuracio_botiga', sa.Column('theme', sa.JSON(), server_default='{}', nullable=False))
    op.add_column('configuracio_botiga', sa.Column('custom_css', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('configuracio_botiga', 'custom_css')
    op.drop_column('configuracio_botiga', 'theme')

"""afegir logo_url a configuracio_botiga

Revision ID: 14115a9c1e29
Revises: 259fe09a2b34
Create Date: 2026-08-27 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '14115a9c1e29'
down_revision: Union[str, None] = '259fe09a2b34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('configuracio_botiga', sa.Column('logo_url', sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column('configuracio_botiga', 'logo_url')

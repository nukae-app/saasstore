"""rename release seccio_id to section_id

Revision ID: eb3f17c1d293
Revises: b45384f7d18d
Create Date: 2026-08-26 06:29:33.142524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'eb3f17c1d293'
down_revision: Union[str, None] = 'b45384f7d18d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('releases', 'seccio_id', new_column_name='section_id')
    op.execute('ALTER INDEX ix_releases_seccio_id RENAME TO ix_releases_section_id')


def downgrade() -> None:
    op.execute('ALTER INDEX ix_releases_section_id RENAME TO ix_releases_seccio_id')
    op.alter_column('releases', 'section_id', new_column_name='seccio_id')

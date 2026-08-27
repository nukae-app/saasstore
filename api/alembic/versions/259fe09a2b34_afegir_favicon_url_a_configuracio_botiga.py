"""afegir favicon_url a configuracio_botiga

Revision ID: 259fe09a2b34
Revises: b060a7859be4
Create Date: 2026-08-27 21:09:05.711405

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '259fe09a2b34'
down_revision: Union[str, None] = 'b060a7859be4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('configuracio_botiga', sa.Column('favicon_url', sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column('configuracio_botiga', 'favicon_url')

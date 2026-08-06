"""mode manteniment: bloqueja compres a no-admins

Revision ID: 043c77e179f3
Revises: b3f2a9c7d1e4
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '043c77e179f3'
down_revision: Union[str, None] = 'b3f2a9c7d1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'configuracio_botiga',
        sa.Column('manteniment_actiu', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('configuracio_botiga', 'manteniment_actiu')

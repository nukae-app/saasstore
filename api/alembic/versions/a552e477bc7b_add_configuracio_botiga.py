"""add_configuracio_botiga

Revision ID: a552e477bc7b
Revises: 9f3d7c2b1a44
Create Date: 2026-07-22 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a552e477bc7b'
down_revision: Union[str, None] = '9f3d7c2b1a44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'configuracio_botiga',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('nom_fiscal', sa.String(length=200), nullable=False),
        sa.Column('nif', sa.String(length=20), nullable=True),
        sa.Column('adreca', sa.Text(), nullable=False),
        sa.Column('telefon', sa.String(length=30), nullable=True),
        sa.Column('email_contacte', sa.String(length=200), nullable=True),
        sa.Column('instagram_url', sa.String(length=300), nullable=True),
        sa.Column('horari', sa.Text(), nullable=True),
        sa.Column('reserva_minuts', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Fila singleton (id=1), sembrada amb els valors que abans vivien a .env.
    op.execute(
        "INSERT INTO configuracio_botiga "
        "(id, nom_fiscal, nif, adreca, telefon, email_contacte, instagram_url, horari, reserva_minuts) "
        "VALUES (1, 'Ultra-Local Records', NULL, 'Pujades 113, 08005 Barcelona', "
        "NULL, NULL, NULL, NULL, 20)"
    )


def downgrade() -> None:
    op.drop_table('configuracio_botiga')

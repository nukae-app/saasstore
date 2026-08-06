"""afegeix seccions (cubetes) i release.seccio_id

Revision ID: a1b2c3d4e5f6
Revises: c94f2a7e1d38
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'c94f2a7e1d38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'seccions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('slug', sa.String(60), nullable=False),
        sa.Column('nom_ca', sa.String(100), nullable=False),
        sa.Column('nom_es', sa.String(100), nullable=True),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('activa', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('posicio', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_seccions_slug', 'seccions', ['slug'], unique=True)
    op.create_index('ix_seccions_activa', 'seccions', ['activa'])

    # Nullable: els releases existents queden sense classificar fins que
    # s'assignin a mà des de l'admin (no hi ha mapeig automàtic des de
    # genero/pais).
    op.add_column('releases', sa.Column('seccio_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_releases_seccio_id_seccions', 'releases', 'seccions',
        ['seccio_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_releases_seccio_id', 'releases', ['seccio_id'])


def downgrade() -> None:
    op.drop_index('ix_releases_seccio_id', 'releases')
    op.drop_constraint('fk_releases_seccio_id_seccions', 'releases', type_='foreignkey')
    op.drop_column('releases', 'seccio_id')
    op.drop_index('ix_seccions_activa', 'seccions')
    op.drop_index('ix_seccions_slug', 'seccions')
    op.drop_table('seccions')

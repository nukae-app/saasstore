"""add_etiquetes_images_properament

Revision ID: 2a7f3c8d1e05
Revises: ed0cb3ae47e4
Create Date: 2026-06-17 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '2a7f3c8d1e05'
down_revision: Union[str, None] = 'ed0cb3ae47e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'etiquetes',
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
    op.create_index('ix_etiquetes_slug', 'etiquetes', ['slug'], unique=True)
    op.create_index('ix_etiquetes_activa', 'etiquetes', ['activa'])

    op.create_table(
        'release_etiquetes',
        sa.Column('release_id', sa.UUID(), nullable=False),
        sa.Column('etiqueta_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['etiqueta_id'], ['etiquetes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('release_id', 'etiqueta_id'),
    )

    op.create_table(
        'release_images',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('release_id', sa.UUID(), nullable=False),
        sa.Column('url', sa.String(800), nullable=False),
        sa.Column('posicio', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tipus', sa.String(40), nullable=True),
        sa.Column('font', sa.String(20), nullable=False, server_default='upload'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_release_images_release_id', 'release_images', ['release_id'])

    op.add_column('releases', sa.Column('properament', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('releases', sa.Column('data_disponibilitat', sa.Date(), nullable=True))
    op.create_index('ix_releases_properament', 'releases', ['properament'])

    # Etiquetes inicials
    op.execute("""
        INSERT INTO etiquetes (slug, nom_ca, nom_es, color, activa, posicio)
        VALUES
            ('novetat',         'Novetat',          'Novedad',          '#10b981', true, 1),
            ('recomanat',       'Recomanat',        'Recomendado',      '#f59e0b', true, 2),
            ('oferta',          'Oferta',           'Oferta',           '#ef4444', true, 3),
            ('staff_pick',      'Staff Pick',       'Staff Pick',       '#8b5cf6', true, 4),
            ('edicio_limitada', 'Edició limitada',  'Edición limitada', '#3b82f6', true, 5)
    """)


def downgrade() -> None:
    op.drop_index('ix_releases_properament', 'releases')
    op.drop_column('releases', 'data_disponibilitat')
    op.drop_column('releases', 'properament')
    op.drop_index('ix_release_images_release_id', 'release_images')
    op.drop_table('release_images')
    op.drop_table('release_etiquetes')
    op.drop_index('ix_etiquetes_activa', 'etiquetes')
    op.drop_index('ix_etiquetes_slug', 'etiquetes')
    op.drop_table('etiquetes')

"""subscripció configurable (periodicitat/quantitat) + pool de catàleg

Revision ID: f412d83dc9a8
Revises: 8fec80176307
Create Date: 2026-07-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f412d83dc9a8'
down_revision: Union[str, None] = '8fec80176307'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `subscripcions_actives` és False i no hi ha cap subscriptor real
    # encara: no cal preservar dades de `plans_subscripcio`/`subscripcions`.
    op.drop_constraint('subscripcions_pla_id_fkey', 'subscripcions', type_='foreignkey')
    op.drop_index('ix_subscripcions_pla_id', table_name='subscripcions')
    op.drop_column('subscripcions', 'pla_id')
    op.drop_table('plans_subscripcio')

    op.create_table(
        'configuracio_subscripcio',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('preu_per_disc', sa.Numeric(10, 2), nullable=False),
        sa.Column('marge_min_pct', sa.Numeric(5, 2), nullable=False, server_default='70'),
        sa.Column('marge_max_pct', sa.Numeric(5, 2), nullable=False, server_default='120'),
        sa.Column('periodicitats_mesos_disponibles', sa.JSON(), nullable=False),
        sa.Column('quantitats_disponibles', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute(
        "INSERT INTO configuracio_subscripcio "
        "(id, preu_per_disc, marge_min_pct, marge_max_pct, periodicitats_mesos_disponibles, quantitats_disponibles) "
        "VALUES (1, 20.00, 70, 120, '[1, 2, 3]', '[1, 2, 3, 4]')"
    )

    op.add_column('subscripcions', sa.Column('periodicitat_mesos', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('subscripcions', sa.Column('quantitat', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('subscripcions', sa.Column('preu_periode', sa.Numeric(10, 2), nullable=False, server_default='0'))
    op.alter_column('subscripcions', 'periodicitat_mesos', server_default=None)
    op.alter_column('subscripcions', 'quantitat', server_default=None)
    op.alter_column('subscripcions', 'preu_periode', server_default=None)

    # Un cobrament (un enviament) ja pot tenir N `Assignacio` (una per disc),
    # no com a molt una.
    op.drop_constraint('subscripcio_assignacions_cobrament_id_key', 'subscripcio_assignacions', type_='unique')
    op.create_index(
        'ix_subscripcio_assignacions_cobrament_id', 'subscripcio_assignacions', ['cobrament_id'],
    )

    op.add_column(
        'items',
        sa.Column('subscripcio_pool', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.create_index('ix_items_subscripcio_pool', 'items', ['subscripcio_pool'])


def downgrade() -> None:
    op.drop_index('ix_items_subscripcio_pool', table_name='items')
    op.drop_column('items', 'subscripcio_pool')

    op.drop_index('ix_subscripcio_assignacions_cobrament_id', table_name='subscripcio_assignacions')
    op.create_unique_constraint(
        'subscripcio_assignacions_cobrament_id_key', 'subscripcio_assignacions', ['cobrament_id'],
    )

    op.drop_column('subscripcions', 'preu_periode')
    op.drop_column('subscripcions', 'quantitat')
    op.drop_column('subscripcions', 'periodicitat_mesos')

    op.drop_table('configuracio_subscripcio')

    op.add_column('subscripcions', sa.Column('pla_id', sa.Integer(), nullable=True))
    op.create_index('ix_subscripcions_pla_id', 'subscripcions', ['pla_id'])
    op.create_table(
        'plans_subscripcio',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nom', sa.String(200), nullable=False),
        sa.Column('preu', sa.Numeric(10, 2), nullable=False),
        sa.Column('periodicitat_dies', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('marge_min_pct', sa.Numeric(5, 2), nullable=False, server_default='70'),
        sa.Column('marge_max_pct', sa.Numeric(5, 2), nullable=False, server_default='120'),
        sa.Column('actiu', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_plans_subscripcio_actiu', 'plans_subscripcio', ['actiu'])
    op.create_foreign_key(
        'subscripcions_pla_id_fkey', 'subscripcions', 'plans_subscripcio', ['pla_id'], ['id'], ondelete='RESTRICT',
    )

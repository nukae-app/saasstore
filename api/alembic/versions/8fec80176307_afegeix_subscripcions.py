"""afegeix subscripcions (club del disc)

Revision ID: 8fec80176307
Revises: a1b2c3d4e5f6
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '8fec80176307'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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

    op.create_table(
        'subscripcions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('pla_id', sa.Integer(), nullable=False),
        sa.Column(
            'estat',
            sa.Enum('pendent_pagament', 'activa', 'pausada', 'cancel_lada', name='estat_subscripcio'),
            nullable=False,
            server_default='pendent_pagament',
        ),
        sa.Column('address_id', sa.Uuid(), nullable=False),
        sa.Column('seccions_preferides', sa.JSON(), nullable=True),
        sa.Column('redsys_identifier', sa.String(40), nullable=True),
        sa.Column('redsys_cof_txnid', sa.String(40), nullable=True),
        sa.Column('proxima_facturacio', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('cancel_lada_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pla_id'], ['plans_subscripcio.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['address_id'], ['addresses.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_subscripcions_user_id', 'subscripcions', ['user_id'])
    op.create_index('ix_subscripcions_pla_id', 'subscripcions', ['pla_id'])
    op.create_index('ix_subscripcions_estat', 'subscripcions', ['estat'])
    op.create_index('ix_subscripcions_proxima_facturacio', 'subscripcions', ['proxima_facturacio'])

    op.create_table(
        'cobraments_subscripcio',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('subscripcio_id', sa.Uuid(), nullable=False),
        sa.Column('periode', sa.Date(), nullable=False),
        sa.Column('import_', sa.Numeric(10, 2), nullable=False),
        sa.Column(
            'estat',
            sa.Enum('pendent', 'cobrat', 'fallit', name='estat_cobrament_subscripcio'),
            nullable=False,
        ),
        sa.Column('ds_order', sa.String(12), nullable=False),
        sa.Column('raw_notification', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['subscripcio_id'], ['subscripcions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ds_order'),
    )
    op.create_index('ix_cobraments_subscripcio_subscripcio_id', 'cobraments_subscripcio', ['subscripcio_id'])
    op.create_index('ix_cobraments_subscripcio_estat', 'cobraments_subscripcio', ['estat'])
    op.create_index('ix_cobraments_subscripcio_ds_order', 'cobraments_subscripcio', ['ds_order'], unique=True)

    op.create_table(
        'subscripcio_assignacions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('cobrament_id', sa.Uuid(), nullable=False),
        sa.Column('subscripcio_id', sa.Uuid(), nullable=False),
        sa.Column('item_id', sa.Uuid(), nullable=True),
        sa.Column('release_id', sa.Uuid(), nullable=True),
        sa.Column(
            'estat',
            sa.Enum('proposada', 'confirmada', 'omesa', 'sense_match', name='estat_assignacio'),
            nullable=False,
            server_default='proposada',
        ),
        sa.Column('order_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('confirmada_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['cobrament_id'], ['cobraments_subscripcio.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscripcio_id'], ['subscripcions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cobrament_id'),
    )
    op.create_index('ix_subscripcio_assignacions_subscripcio_id', 'subscripcio_assignacions', ['subscripcio_id'])
    op.create_index('ix_subscripcio_assignacions_release_id', 'subscripcio_assignacions', ['release_id'])
    op.create_index('ix_subscripcio_assignacions_estat', 'subscripcio_assignacions', ['estat'])

    # Reserva d'un item mentre l'admin revisa una proposta d'assignació
    # (mateix patró que items.reserved_for_peticion_id): cal use_alter perquè
    # subscripcio_assignacions ja referencia items.id.
    op.add_column('items', sa.Column('reserved_for_assignacio_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_items_reserved_for_assignacio_id', 'items', 'subscripcio_assignacions',
        ['reserved_for_assignacio_id'], ['id'], ondelete='SET NULL',
    )

    op.add_column(
        'configuracio_botiga',
        sa.Column('subscripcions_actives', sa.Boolean(), nullable=False, server_default='false'),
    )

    op.execute("ALTER TYPE order_origen ADD VALUE IF NOT EXISTS 'subscripcio'")


def downgrade() -> None:
    # Postgres no permet treure valors d'un ENUM sense recrear el tipus;
    # no cal desfer l'ADD VALUE de order_origen per a una migració additiva.
    op.drop_column('configuracio_botiga', 'subscripcions_actives')
    op.drop_constraint('fk_items_reserved_for_assignacio_id', 'items', type_='foreignkey')
    op.drop_column('items', 'reserved_for_assignacio_id')
    op.drop_index('ix_subscripcio_assignacions_estat', 'subscripcio_assignacions')
    op.drop_index('ix_subscripcio_assignacions_release_id', 'subscripcio_assignacions')
    op.drop_index('ix_subscripcio_assignacions_subscripcio_id', 'subscripcio_assignacions')
    op.drop_table('subscripcio_assignacions')
    sa.Enum(name='estat_assignacio').drop(op.get_bind(), checkfirst=True)
    op.drop_index('ix_cobraments_subscripcio_ds_order', 'cobraments_subscripcio')
    op.drop_index('ix_cobraments_subscripcio_estat', 'cobraments_subscripcio')
    op.drop_index('ix_cobraments_subscripcio_subscripcio_id', 'cobraments_subscripcio')
    op.drop_table('cobraments_subscripcio')
    sa.Enum(name='estat_cobrament_subscripcio').drop(op.get_bind(), checkfirst=True)
    op.drop_index('ix_subscripcions_proxima_facturacio', 'subscripcions')
    op.drop_index('ix_subscripcions_estat', 'subscripcions')
    op.drop_index('ix_subscripcions_pla_id', 'subscripcions')
    op.drop_index('ix_subscripcions_user_id', 'subscripcions')
    op.drop_table('subscripcions')
    sa.Enum(name='estat_subscripcio').drop(op.get_bind(), checkfirst=True)
    op.drop_index('ix_plans_subscripcio_actiu', 'plans_subscripcio')
    op.drop_table('plans_subscripcio')

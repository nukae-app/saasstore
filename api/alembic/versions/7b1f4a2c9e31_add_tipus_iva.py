"""add_tipus_iva

Revision ID: 7b1f4a2c9e31
Revises: 3def99e90fac
Create Date: 2026-06-18 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7b1f4a2c9e31'
down_revision: Union[str, None] = '3def99e90fac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tipus_iva',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nom', sa.String(length=200), nullable=False),
        sa.Column('percentatge', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('es_rebu', sa.Boolean(), nullable=False),
        sa.Column('per_defecte_nou', sa.Boolean(), nullable=False),
        sa.Column('per_defecte_segona_ma', sa.Boolean(), nullable=False),
        sa.Column('actiu', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tipus_iva_es_rebu'), 'tipus_iva', ['es_rebu'], unique=False)
    op.create_index(op.f('ix_tipus_iva_per_defecte_nou'), 'tipus_iva', ['per_defecte_nou'], unique=False)
    op.create_index(op.f('ix_tipus_iva_per_defecte_segona_ma'), 'tipus_iva', ['per_defecte_segona_ma'], unique=False)
    op.create_index(op.f('ix_tipus_iva_actiu'), 'tipus_iva', ['actiu'], unique=False)

    # Seed: els dos tipus que ja s'assumien implícitament al codi (general 21%,
    # i un tipus REBU per a 2a mà sobre marge), perquè les vendes/compres futures
    # tinguin un tipus per defecte des del primer moment.
    op.execute(
        "INSERT INTO tipus_iva (nom, percentatge, es_rebu, per_defecte_nou, per_defecte_segona_ma, actiu) "
        "VALUES ('General 21% (discos nous)', 21.00, false, true, false, true)"
    )
    op.execute(
        "INSERT INTO tipus_iva (nom, percentatge, es_rebu, per_defecte_nou, per_defecte_segona_ma, actiu) "
        "VALUES ('REBU 21% (2a mà - marge)', 21.00, true, false, true, true)"
    )

    op.add_column('despeses', sa.Column('tipus_iva_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_despeses_tipus_iva_id'), 'despeses', ['tipus_iva_id'], unique=False)
    op.create_foreign_key(
        'fk_despeses_tipus_iva_id', 'despeses', 'tipus_iva', ['tipus_iva_id'], ['id'], ondelete='SET NULL'
    )

    op.add_column('order_items', sa.Column('tipus_iva_id', sa.Integer(), nullable=True))
    op.add_column('order_items', sa.Column('iva_pct', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('order_items', sa.Column('iva_import', sa.Numeric(precision=10, scale=2), nullable=True))
    op.create_index(op.f('ix_order_items_tipus_iva_id'), 'order_items', ['tipus_iva_id'], unique=False)
    op.create_foreign_key(
        'fk_order_items_tipus_iva_id', 'order_items', 'tipus_iva', ['tipus_iva_id'], ['id'], ondelete='SET NULL'
    )

    op.add_column('ventas_externas', sa.Column('tipus_iva_id', sa.Integer(), nullable=True))
    op.add_column('ventas_externas', sa.Column('iva_pct', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('ventas_externas', sa.Column('iva_import', sa.Numeric(precision=10, scale=2), nullable=True))
    op.create_index(op.f('ix_ventas_externas_tipus_iva_id'), 'ventas_externas', ['tipus_iva_id'], unique=False)
    op.create_foreign_key(
        'fk_ventas_externas_tipus_iva_id', 'ventas_externas', 'tipus_iva', ['tipus_iva_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_ventas_externas_tipus_iva_id', 'ventas_externas', type_='foreignkey')
    op.drop_index(op.f('ix_ventas_externas_tipus_iva_id'), table_name='ventas_externas')
    op.drop_column('ventas_externas', 'iva_import')
    op.drop_column('ventas_externas', 'iva_pct')
    op.drop_column('ventas_externas', 'tipus_iva_id')

    op.drop_constraint('fk_order_items_tipus_iva_id', 'order_items', type_='foreignkey')
    op.drop_index(op.f('ix_order_items_tipus_iva_id'), table_name='order_items')
    op.drop_column('order_items', 'iva_import')
    op.drop_column('order_items', 'iva_pct')
    op.drop_column('order_items', 'tipus_iva_id')

    op.drop_constraint('fk_despeses_tipus_iva_id', 'despeses', type_='foreignkey')
    op.drop_index(op.f('ix_despeses_tipus_iva_id'), table_name='despeses')
    op.drop_column('despeses', 'tipus_iva_id')

    op.drop_index(op.f('ix_tipus_iva_actiu'), table_name='tipus_iva')
    op.drop_index(op.f('ix_tipus_iva_per_defecte_segona_ma'), table_name='tipus_iva')
    op.drop_index(op.f('ix_tipus_iva_per_defecte_nou'), table_name='tipus_iva')
    op.drop_index(op.f('ix_tipus_iva_es_rebu'), table_name='tipus_iva')
    op.drop_table('tipus_iva')

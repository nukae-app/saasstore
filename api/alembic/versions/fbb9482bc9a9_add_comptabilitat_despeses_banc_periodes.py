"""add_comptabilitat_despeses_banc_periodes

Revision ID: fbb9482bc9a9
Revises: bc8be2cee0cc
Create Date: 2026-06-13 21:08:26.601173

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fbb9482bc9a9'
down_revision: Union[str, None] = 'bc8be2cee0cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('comptes_bancaris',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nom', sa.String(length=200), nullable=False),
    sa.Column('iban', sa.String(length=34), nullable=True),
    sa.Column('entitat', sa.String(length=100), nullable=True),
    sa.Column('actiu', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('saldo_inicial', sa.Numeric(precision=12, scale=2), server_default=sa.text('0'), nullable=False),
    sa.Column('data_saldo_inicial', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('periodes_comptables',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('mes', sa.Integer(), nullable=False),
    sa.Column('tancat', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('data_tancament', sa.DateTime(timezone=True), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('year', 'mes')
    )
    op.create_index(op.f('ix_periodes_comptables_mes'), 'periodes_comptables', ['mes'], unique=False)
    op.create_index(op.f('ix_periodes_comptables_tancat'), 'periodes_comptables', ['tancat'], unique=False)
    op.create_index(op.f('ix_periodes_comptables_year'), 'periodes_comptables', ['year'], unique=False)
    op.create_table('despeses',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('num_factura', sa.String(length=200), nullable=True),
    sa.Column('data_factura', sa.Date(), nullable=False),
    sa.Column('data_venciment', sa.Date(), nullable=True),
    sa.Column('proveidor_id', sa.Uuid(), nullable=True),
    sa.Column('proveidor_nom', sa.String(length=300), nullable=False),
    sa.Column('categoria', sa.Enum('compres_material', 'subministraments', 'lloguer', 'comunicacions', 'serveis_professionals', 'transport', 'material_oficina', 'publicitat', 'altres', name='categoria_despesa'), nullable=False),
    sa.Column('concepte', sa.String(length=500), nullable=False),
    sa.Column('base_imposable', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('iva_pct', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('iva_import', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('total', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('estat_pagament', sa.Enum('pendent', 'pagat', 'vencut', name='estat_pagament_despesa'), server_default='pendent', nullable=False),
    sa.Column('data_pagament', sa.Date(), nullable=True),
    sa.Column('metode_pagament', sa.String(length=30), nullable=True),
    sa.Column('compra_id', sa.Uuid(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['compra_id'], ['compras.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['proveidor_id'], ['proveedores.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_despeses_categoria'), 'despeses', ['categoria'], unique=False)
    op.create_index(op.f('ix_despeses_compra_id'), 'despeses', ['compra_id'], unique=True)
    op.create_index(op.f('ix_despeses_data_factura'), 'despeses', ['data_factura'], unique=False)
    op.create_index(op.f('ix_despeses_data_venciment'), 'despeses', ['data_venciment'], unique=False)
    op.create_index(op.f('ix_despeses_estat_pagament'), 'despeses', ['estat_pagament'], unique=False)
    op.create_index(op.f('ix_despeses_num_factura'), 'despeses', ['num_factura'], unique=False)
    op.create_index(op.f('ix_despeses_proveidor_id'), 'despeses', ['proveidor_id'], unique=False)
    op.create_table('moviments_bancaris',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('compte_id', sa.Integer(), nullable=False),
    sa.Column('data_operacio', sa.Date(), nullable=False),
    sa.Column('data_valor', sa.Date(), nullable=True),
    sa.Column('concepte', sa.String(length=500), nullable=False),
    sa.Column('import_moviment', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('saldo', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('estat', sa.Enum('pendent', 'conciliat', 'ignorat', name='estat_conciliacio'), server_default='pendent', nullable=False),
    sa.Column('despesa_id', sa.Uuid(), nullable=True),
    sa.Column('order_id', sa.Uuid(), nullable=True),
    sa.Column('venta_externa_id', sa.Uuid(), nullable=True),
    sa.Column('notes_conciliacio', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['compte_id'], ['comptes_bancaris.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['despesa_id'], ['despeses.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['venta_externa_id'], ['ventas_externas.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_moviments_bancaris_compte_id'), 'moviments_bancaris', ['compte_id'], unique=False)
    op.create_index(op.f('ix_moviments_bancaris_data_operacio'), 'moviments_bancaris', ['data_operacio'], unique=False)
    op.create_index(op.f('ix_moviments_bancaris_despesa_id'), 'moviments_bancaris', ['despesa_id'], unique=False)
    op.create_index(op.f('ix_moviments_bancaris_estat'), 'moviments_bancaris', ['estat'], unique=False)
    op.create_index(op.f('ix_moviments_bancaris_order_id'), 'moviments_bancaris', ['order_id'], unique=False)
    op.create_index(op.f('ix_moviments_bancaris_venta_externa_id'), 'moviments_bancaris', ['venta_externa_id'], unique=False)
    # rebu: columna NOT NULL — server_default='false' per a files existents
    op.add_column('items', sa.Column('rebu', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.create_index(op.f('ix_items_rebu'), 'items', ['rebu'], unique=False)
    op.add_column('orders', sa.Column('cobrat_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('proveedores', sa.Column('nif', sa.String(length=20), nullable=True))
    op.add_column('proveedores', sa.Column('email', sa.String(length=320), nullable=True))
    op.add_column('proveedores', sa.Column('telefon', sa.String(length=40), nullable=True))
    # actiu: server_default='true' per a proveïdors existents
    op.add_column('proveedores', sa.Column('actiu', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('proveedores', sa.Column('iban_proveidor', sa.String(length=34), nullable=True))
    op.add_column('proveedores', sa.Column('metode_pagament', sa.String(length=30), nullable=True))
    op.add_column('proveedores', sa.Column('dies_pagament', sa.Integer(), nullable=True))
    op.add_column('proveedores', sa.Column('dia_pagament_mes', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_proveedores_actiu'), 'proveedores', ['actiu'], unique=False)
    op.add_column('ventas_externas', sa.Column('cobrat_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('ventas_externas', 'cobrat_at')
    op.drop_index(op.f('ix_proveedores_actiu'), table_name='proveedores')
    op.drop_column('proveedores', 'dia_pagament_mes')
    op.drop_column('proveedores', 'dies_pagament')
    op.drop_column('proveedores', 'metode_pagament')
    op.drop_column('proveedores', 'iban_proveidor')
    op.drop_column('proveedores', 'actiu')
    op.drop_column('proveedores', 'telefon')
    op.drop_column('proveedores', 'email')
    op.drop_column('proveedores', 'nif')
    op.drop_column('orders', 'cobrat_at')
    op.drop_index(op.f('ix_items_rebu'), table_name='items')
    op.drop_column('items', 'rebu')
    op.drop_index(op.f('ix_moviments_bancaris_venta_externa_id'), table_name='moviments_bancaris')
    op.drop_index(op.f('ix_moviments_bancaris_order_id'), table_name='moviments_bancaris')
    op.drop_index(op.f('ix_moviments_bancaris_estat'), table_name='moviments_bancaris')
    op.drop_index(op.f('ix_moviments_bancaris_despesa_id'), table_name='moviments_bancaris')
    op.drop_index(op.f('ix_moviments_bancaris_data_operacio'), table_name='moviments_bancaris')
    op.drop_index(op.f('ix_moviments_bancaris_compte_id'), table_name='moviments_bancaris')
    op.drop_table('moviments_bancaris')
    op.drop_index(op.f('ix_despeses_proveidor_id'), table_name='despeses')
    op.drop_index(op.f('ix_despeses_num_factura'), table_name='despeses')
    op.drop_index(op.f('ix_despeses_estat_pagament'), table_name='despeses')
    op.drop_index(op.f('ix_despeses_data_venciment'), table_name='despeses')
    op.drop_index(op.f('ix_despeses_data_factura'), table_name='despeses')
    op.drop_index(op.f('ix_despeses_compra_id'), table_name='despeses')
    op.drop_index(op.f('ix_despeses_categoria'), table_name='despeses')
    op.drop_table('despeses')
    op.drop_index(op.f('ix_periodes_comptables_year'), table_name='periodes_comptables')
    op.drop_index(op.f('ix_periodes_comptables_tancat'), table_name='periodes_comptables')
    op.drop_index(op.f('ix_periodes_comptables_mes'), table_name='periodes_comptables')
    op.drop_table('periodes_comptables')
    op.drop_table('comptes_bancaris')
    op.drop_enum('estat_conciliacio')
    op.drop_enum('estat_pagament_despesa')
    op.drop_enum('categoria_despesa')

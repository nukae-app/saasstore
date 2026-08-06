"""add_comandas_y_comanda_items

Revision ID: d236b94dc2a4
Revises: 2a7f3c8d1e05
Create Date: 2026-06-18 08:44:31.738467

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd236b94dc2a4'
down_revision: Union[str, None] = '2a7f3c8d1e05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('comandas',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('proveedor_id', sa.Uuid(), nullable=False),
    sa.Column('fecha', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Enum('esborrany', 'enviada', 'rebuda_parcial', 'rebuda', 'cancelada', name='estado_comanda'), nullable=False),
    sa.Column('num_comanda', sa.String(length=100), nullable=True),
    sa.Column('notas', sa.Text(), nullable=True),
    sa.Column('enviada_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['proveedor_id'], ['proveedores.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comandas_fecha'), 'comandas', ['fecha'], unique=False)
    op.create_index(op.f('ix_comandas_proveedor_id'), 'comandas', ['proveedor_id'], unique=False)
    op.create_index(op.f('ix_comandas_status'), 'comandas', ['status'], unique=False)
    op.create_table('comanda_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('comanda_id', sa.Uuid(), nullable=False),
    sa.Column('release_id', sa.Uuid(), nullable=False),
    sa.Column('cantidad', sa.Integer(), nullable=False),
    sa.Column('precio_unitario_estimado', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('cantidad_rebuda', sa.Integer(), nullable=False),
    sa.Column('notas', sa.String(length=300), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['comanda_id'], ['comandas.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comanda_items_comanda_id'), 'comanda_items', ['comanda_id'], unique=False)
    op.create_index(op.f('ix_comanda_items_release_id'), 'comanda_items', ['release_id'], unique=False)
    op.add_column('compras', sa.Column('comanda_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_compras_comanda_id'), 'compras', ['comanda_id'], unique=False)
    op.create_foreign_key('fk_compras_comanda_id', 'compras', 'comandas', ['comanda_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_compras_comanda_id', 'compras', type_='foreignkey')
    op.drop_index(op.f('ix_compras_comanda_id'), table_name='compras')
    op.drop_column('compras', 'comanda_id')
    op.drop_index(op.f('ix_comanda_items_release_id'), table_name='comanda_items')
    op.drop_index(op.f('ix_comanda_items_comanda_id'), table_name='comanda_items')
    op.drop_table('comanda_items')
    op.drop_index(op.f('ix_comandas_status'), table_name='comandas')
    op.drop_index(op.f('ix_comandas_proveedor_id'), table_name='comandas')
    op.drop_index(op.f('ix_comandas_fecha'), table_name='comandas')
    op.drop_table('comandas')
    sa.Enum(name='estado_comanda').drop(op.get_bind(), checkfirst=True)

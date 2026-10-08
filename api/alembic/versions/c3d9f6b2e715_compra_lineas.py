"""compra_lineas

Detall per recepció (quantitat, cost unitari i PVP fixats): la font del PDF de
recepció. `Item` per a discos nous és stock agregat i no permet saber què va
entrar en cada recepció concreta.

Revision ID: c3d9f6b2e715
Revises: f7d4b1e83c69
Create Date: 2026-10-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d9f6b2e715'
down_revision: Union[str, None] = 'f7d4b1e83c69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'compra_lineas',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('compra_id', sa.Uuid(), nullable=False),
        sa.Column('item_id', sa.Uuid(), nullable=True),
        sa.Column('release_id', sa.Uuid(), nullable=False),
        sa.Column('condition', sa.String(length=20), nullable=False),
        sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
        sa.Column('acquisition_cost', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('estado_disco', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['compra_id'], ['compras.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_compra_lineas_compra_id'), 'compra_lineas', ['compra_id'], unique=False)
    op.create_index(op.f('ix_compra_lineas_item_id'), 'compra_lineas', ['item_id'], unique=False)
    op.create_index(op.f('ix_compra_lineas_release_id'), 'compra_lineas', ['release_id'], unique=False)
    op.create_index(op.f('ix_compra_lineas_tenant_id'), 'compra_lineas', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_compra_lineas_tenant_id'), table_name='compra_lineas')
    op.drop_index(op.f('ix_compra_lineas_release_id'), table_name='compra_lineas')
    op.drop_index(op.f('ix_compra_lineas_item_id'), table_name='compra_lineas')
    op.drop_index(op.f('ix_compra_lineas_compra_id'), table_name='compra_lineas')
    op.drop_table('compra_lineas')

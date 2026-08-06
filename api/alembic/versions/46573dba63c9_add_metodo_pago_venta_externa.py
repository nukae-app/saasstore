"""add_metodo_pago_venta_externa

Revision ID: 46573dba63c9
Revises: cf929c5314c0
Create Date: 2026-06-11 13:15:58.359089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '46573dba63c9'
down_revision: Union[str, None] = 'cf929c5314c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    metodo_pago_enum = sa.Enum('efectivo', 'tarjeta', name='metodo_pago')
    metodo_pago_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('ventas_externas', sa.Column('metodo_pago', metodo_pago_enum, nullable=False, server_default='efectivo'))
    op.create_index(op.f('ix_ventas_externas_metodo_pago'), 'ventas_externas', ['metodo_pago'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ventas_externas_metodo_pago'), table_name='ventas_externas')
    op.drop_column('ventas_externas', 'metodo_pago')
    sa.Enum(name='metodo_pago').drop(op.get_bind(), checkfirst=True)

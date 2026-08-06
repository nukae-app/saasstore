"""add_direccion_proveedor_num_comanda_unique

Revision ID: 3def99e90fac
Revises: d236b94dc2a4
Create Date: 2026-06-18 10:10:42.047875

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3def99e90fac'
down_revision: Union[str, None] = 'd236b94dc2a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('comandas', 'num_comanda',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=20),
               nullable=False)
    op.create_index(op.f('ix_comandas_num_comanda'), 'comandas', ['num_comanda'], unique=True)
    op.add_column('proveedores', sa.Column('direccion', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('proveedores', 'direccion')
    op.drop_index(op.f('ix_comandas_num_comanda'), table_name='comandas')
    op.alter_column('comandas', 'num_comanda',
               existing_type=sa.String(length=20),
               type_=sa.VARCHAR(length=100),
               nullable=True)

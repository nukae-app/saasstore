"""zona nacional/internacional a trams_enviament i treu camps de Correos

Revision ID: b7e21f4c9a06
Revises: 707539b40f03
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e21f4c9a06'
down_revision: Union[str, None] = '707539b40f03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'trams_enviament',
        sa.Column('zona', sa.String(length=20), server_default='nacional', nullable=False),
    )
    op.create_index(op.f('ix_trams_enviament_zona'), 'trams_enviament', ['zona'], unique=False)
    op.drop_column('orders', 'correos_shipment_id')
    op.drop_column('orders', 'correos_label_status')
    op.drop_column('orders', 'correos_raw_response')


def downgrade() -> None:
    op.add_column('orders', sa.Column('correos_raw_response', sa.JSON(), nullable=True))
    op.add_column('orders', sa.Column('correos_label_status', sa.String(length=40), nullable=True))
    op.add_column('orders', sa.Column('correos_shipment_id', sa.String(length=80), nullable=True))
    op.drop_index(op.f('ix_trams_enviament_zona'), table_name='trams_enviament')
    op.drop_column('trams_enviament', 'zona')

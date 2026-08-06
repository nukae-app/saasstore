"""caixa_diaria

Revision ID: b3f2a9c7d1e4
Revises: aa37c7aded56
Create Date: 2026-08-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3f2a9c7d1e4'
down_revision: Union[str, None] = 'aa37c7aded56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'caixa_diaria',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('data', sa.Date(), nullable=False),
        sa.Column('targeta_21', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('targeta_4', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('efectiu_21', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('efectiu_4', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('bizum_21', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('bizum_4', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('paypal_21', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('paypal_4', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('transfer_21', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('bono_cultural', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_caixa_diaria_data', 'caixa_diaria', ['data'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_caixa_diaria_data', table_name='caixa_diaria')
    op.drop_table('caixa_diaria')

"""afegir taula home_blocks

Revision ID: 42d56e3f1a28
Revises: 230eb4cfc0b5
Create Date: 2026-08-28 07:20:34.726088

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '42d56e3f1a28'
down_revision: Union[str, None] = '230eb4cfc0b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('home_blocks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('block_type', sa.String(length=60), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('props', sa.JSON(), server_default='{}', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_home_blocks_block_type'), 'home_blocks', ['block_type'], unique=False)
    op.create_index(op.f('ix_home_blocks_tenant_id'), 'home_blocks', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_home_blocks_tenant_id'), table_name='home_blocks')
    op.drop_index(op.f('ix_home_blocks_block_type'), table_name='home_blocks')
    op.drop_table('home_blocks')

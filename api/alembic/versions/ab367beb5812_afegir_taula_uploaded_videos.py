"""afegir_taula_uploaded_videos

Revision ID: ab367beb5812
Revises: 9f3a7c1d5e2b
Create Date: 2026-08-28 21:40:56.886696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ab367beb5812'
down_revision: Union[str, None] = '9f3a7c1d5e2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('uploaded_videos',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('url', sa.String(length=500), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_uploaded_videos_tenant_id'), 'uploaded_videos', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_uploaded_videos_tenant_id'), table_name='uploaded_videos')
    op.drop_table('uploaded_videos')

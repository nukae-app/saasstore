"""channel_backups

Copias de seguridad del catálogo de cada tenant (releases, items, vínculos con Discogs y listings) y del
inventario de Discogs, guardadas en la app para poder restaurar el catálogo (docs/PLAN_CANAL_DISCOGS.md).
Solo datos del propio tenant: nunca toda la base de datos.

Revision ID: f7d4b1e83c69
Revises: e6c3a9d42b58
Create Date: 2026-10-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7d4b1e83c69'
down_revision: Union[str, None] = 'e6c3a9d42b58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'channel_backups',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('channel', sa.String(length=30), server_default='discogs', nullable=False),
        sa.Column('kind', sa.String(length=24), nullable=False),
        sa.Column('trigger', sa.String(length=24), server_default='manual', nullable=False),
        sa.Column('label', sa.String(length=200), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('payload', sa.LargeBinary(), nullable=True),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_channel_backups_channel'), 'channel_backups', ['channel'], unique=False)
    op.create_index(op.f('ix_channel_backups_kind'), 'channel_backups', ['kind'], unique=False)
    op.create_index(op.f('ix_channel_backups_created_at'), 'channel_backups', ['created_at'], unique=False)
    op.create_index(op.f('ix_channel_backups_tenant_id'), 'channel_backups', ['tenant_id'], unique=False)

    if op.get_bind().dialect.name == 'postgresql':
        op.execute("ALTER TABLE channel_backups ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE channel_backups FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON channel_backups "
            "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON channel_backups")
        op.execute("ALTER TABLE channel_backups NO FORCE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE channel_backups DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f('ix_channel_backups_tenant_id'), table_name='channel_backups')
    op.drop_index(op.f('ix_channel_backups_created_at'), table_name='channel_backups')
    op.drop_index(op.f('ix_channel_backups_kind'), table_name='channel_backups')
    op.drop_index(op.f('ix_channel_backups_channel'), table_name='channel_backups')
    op.drop_table('channel_backups')

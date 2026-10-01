"""channel_settings

Ajustes por tenant y canal del centro de control de ventas online
(docs/PLAN_CANAL_DISCOGS.md): publicación automática (apagada por defecto),
retirada programada, recargo, sondeo de pedidos y su cursor.

Revision ID: d5b2f8c31a47
Revises: c3d9a7e15f28
Create Date: 2026-10-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5b2f8c31a47'
down_revision: Union[str, None] = 'c3d9a7e15f28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'channel_settings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('channel', sa.String(length=30), server_default='discogs', nullable=False),
        sa.Column('publicacion_auto', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('sync_auto', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('recargo_pct', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
        sa.Column('orders_auto', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('orders_poll_minutes', sa.Integer(), server_default='10', nullable=False),
        sa.Column('orders_cursor', sa.DateTime(timezone=True), nullable=True),
        sa.Column('orders_last_pull_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('orders_last_result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'channel'),
    )
    op.create_index(op.f('ix_channel_settings_tenant_id'), 'channel_settings', ['tenant_id'], unique=False)

    if op.get_bind().dialect.name == 'postgresql':
        op.execute("ALTER TABLE channel_settings ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE channel_settings FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON channel_settings "
            "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON channel_settings")
        op.execute("ALTER TABLE channel_settings NO FORCE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE channel_settings DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f('ix_channel_settings_tenant_id'), table_name='channel_settings')
    op.drop_table('channel_settings')

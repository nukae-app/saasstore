"""channel_alerts_notification_prefs

Bandeja de alertas del canal (excepciones accionables, deduplicadas por `ref_key`) y preferencias
de aviso por usuario (docs/PLAN_CANAL_DISCOGS.md, fase E).

Revision ID: e6c3a9d42b58
Revises: d5b2f8c31a47
Create Date: 2026-10-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6c3a9d42b58'
down_revision: Union[str, None] = 'd5b2f8c31a47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_TABLES = ['channel_alerts', 'notification_prefs']


def upgrade() -> None:
    op.create_table(
        'channel_alerts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('channel', sa.String(length=30), server_default='discogs', nullable=False),
        sa.Column('kind', sa.String(length=40), nullable=False),
        sa.Column('severity', sa.String(length=10), server_default='warning', nullable=False),
        sa.Column('ref_key', sa.String(length=160), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('item_id', sa.Uuid(), nullable=True),
        sa.Column('order_id', sa.Uuid(), nullable=True),
        sa.Column('external_id', sa.String(length=60), nullable=True),
        sa.Column('status', sa.String(length=12), server_default='open', nullable=False),
        sa.Column('occurrences', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'channel', 'ref_key'),
    )
    op.create_index(op.f('ix_channel_alerts_kind'), 'channel_alerts', ['kind'], unique=False)
    op.create_index(op.f('ix_channel_alerts_status'), 'channel_alerts', ['status'], unique=False)
    op.create_index(op.f('ix_channel_alerts_item_id'), 'channel_alerts', ['item_id'], unique=False)
    op.create_index(op.f('ix_channel_alerts_order_id'), 'channel_alerts', ['order_id'], unique=False)
    op.create_index(op.f('ix_channel_alerts_tenant_id'), 'channel_alerts', ['tenant_id'], unique=False)

    op.create_table(
        'notification_prefs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('event_key', sa.String(length=40), nullable=False),
        sa.Column('email', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'user_id', 'event_key'),
    )
    op.create_index(op.f('ix_notification_prefs_user_id'), 'notification_prefs', ['user_id'], unique=False)
    op.create_index(op.f('ix_notification_prefs_tenant_id'), 'notification_prefs', ['tenant_id'], unique=False)

    if op.get_bind().dialect.name == 'postgresql':
        for table in NEW_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} "
                f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        for table in NEW_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f('ix_notification_prefs_tenant_id'), table_name='notification_prefs')
    op.drop_index(op.f('ix_notification_prefs_user_id'), table_name='notification_prefs')
    op.drop_table('notification_prefs')
    op.drop_index(op.f('ix_channel_alerts_tenant_id'), table_name='channel_alerts')
    op.drop_index(op.f('ix_channel_alerts_order_id'), table_name='channel_alerts')
    op.drop_index(op.f('ix_channel_alerts_item_id'), table_name='channel_alerts')
    op.drop_index(op.f('ix_channel_alerts_status'), table_name='channel_alerts')
    op.drop_index(op.f('ix_channel_alerts_kind'), table_name='channel_alerts')
    op.drop_table('channel_alerts')

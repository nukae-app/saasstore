"""channel_listings_events_runs

Fase A del centro de control de canales (docs/PLAN_CANAL_DISCOGS.md §5):
tablas genéricas de canal `channel_listings` (vínculo item ↔ publicación, con
estado), `channel_events` (registro de actividad) y `channel_sync_runs`
(historial persistente de sincronizaciones). Copia los `codi_discogs`
existentes a `channel_listings` (estado `publicat`); `codi_discogs` sigue
siendo la columna en uso hasta que el reconciliador sea quien escriba.

Revision ID: c3d9a7e15f28
Revises: b2c8e5a1d604
Create Date: 2026-10-01 00:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d9a7e15f28'
down_revision: Union[str, None] = 'b2c8e5a1d604'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_TABLES = ['channel_listings', 'channel_events', 'channel_sync_runs']


def upgrade() -> None:
    op.create_table(
        'channel_listings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('item_id', sa.Uuid(), nullable=False),
        sa.Column('channel', sa.String(length=30), server_default='discogs', nullable=False),
        sa.Column('external_id', sa.String(length=60), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pendent', nullable=False),
        sa.Column('published_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('published_condition', sa.String(length=60), nullable=True),
        sa.Column('published_sleeve', sa.String(length=60), nullable=True),
        sa.Column('desired_hash', sa.String(length=64), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'channel', 'item_id'),
        sa.UniqueConstraint('tenant_id', 'channel', 'external_id'),
    )
    op.create_index(op.f('ix_channel_listings_item_id'), 'channel_listings', ['item_id'], unique=False)
    op.create_index(op.f('ix_channel_listings_status'), 'channel_listings', ['status'], unique=False)
    op.create_index(op.f('ix_channel_listings_tenant_id'), 'channel_listings', ['tenant_id'], unique=False)

    op.create_table(
        'channel_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('channel', sa.String(length=30), server_default='discogs', nullable=False),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('outcome', sa.String(length=20), nullable=False),
        sa.Column('item_id', sa.Uuid(), nullable=True),
        sa.Column('order_id', sa.Uuid(), nullable=True),
        sa.Column('external_id', sa.String(length=60), nullable=True),
        sa.Column('actor', sa.String(length=120), nullable=True),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_channel_events_channel'), 'channel_events', ['channel'], unique=False)
    op.create_index(op.f('ix_channel_events_action'), 'channel_events', ['action'], unique=False)
    op.create_index(op.f('ix_channel_events_outcome'), 'channel_events', ['outcome'], unique=False)
    op.create_index(op.f('ix_channel_events_item_id'), 'channel_events', ['item_id'], unique=False)
    op.create_index(op.f('ix_channel_events_order_id'), 'channel_events', ['order_id'], unique=False)
    op.create_index(op.f('ix_channel_events_created_at'), 'channel_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_channel_events_tenant_id'), 'channel_events', ['tenant_id'], unique=False)

    op.create_table(
        'channel_sync_runs',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('channel', sa.String(length=30), server_default='discogs', nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='queued', nullable=False),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('error_kind', sa.String(length=20), nullable=True),
        sa.Column('rows_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('report', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_channel_sync_runs_channel'), 'channel_sync_runs', ['channel'], unique=False)
    op.create_index(op.f('ix_channel_sync_runs_created_at'), 'channel_sync_runs', ['created_at'], unique=False)
    op.create_index(op.f('ix_channel_sync_runs_tenant_id'), 'channel_sync_runs', ['tenant_id'], unique=False)

    # Copia de los vínculos actuales (codi_discogs -> channel_listings). Los ids se
    # generan en Python (gen_random_uuid() no existe en todas las versiones de
    # Postgres sin extensión). Se hace ANTES de activar RLS: la migración no
    # tiene `app.tenant_id` puesto y la política bloquearía el INSERT.
    bind = op.get_bind()
    filas = bind.execute(sa.text(
        "SELECT d.item_id, i.tenant_id, d.codi_discogs, i.price "
        "FROM record_stock_details d JOIN items i ON i.id = d.item_id "
        "WHERE d.codi_discogs IS NOT NULL"
    )).fetchall()
    if filas:
        listings = sa.table(
            'channel_listings',
            sa.column('id', sa.Uuid()), sa.column('item_id', sa.Uuid()), sa.column('tenant_id', sa.Uuid()),
            sa.column('channel', sa.String()), sa.column('external_id', sa.String()),
            sa.column('status', sa.String()), sa.column('published_price', sa.Numeric()),
        )
        op.bulk_insert(listings, [
            {
                'id': uuid.uuid4(), 'item_id': f.item_id, 'tenant_id': f.tenant_id, 'channel': 'discogs',
                'external_id': str(f.codi_discogs), 'status': 'publicat', 'published_price': f.price,
            }
            for f in filas
        ])

    # RLS en Postgres: mismo cinturón que el resto de tablas por tenant (ver
    # 9ee2df1716bf_multi_tenant_core_tenant_id.py).
    if bind.dialect.name == 'postgresql':
        for table in NEW_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} "
                f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        for table in NEW_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index(op.f('ix_channel_sync_runs_tenant_id'), table_name='channel_sync_runs')
    op.drop_index(op.f('ix_channel_sync_runs_created_at'), table_name='channel_sync_runs')
    op.drop_index(op.f('ix_channel_sync_runs_channel'), table_name='channel_sync_runs')
    op.drop_table('channel_sync_runs')

    op.drop_index(op.f('ix_channel_events_tenant_id'), table_name='channel_events')
    op.drop_index(op.f('ix_channel_events_created_at'), table_name='channel_events')
    op.drop_index(op.f('ix_channel_events_order_id'), table_name='channel_events')
    op.drop_index(op.f('ix_channel_events_item_id'), table_name='channel_events')
    op.drop_index(op.f('ix_channel_events_outcome'), table_name='channel_events')
    op.drop_index(op.f('ix_channel_events_action'), table_name='channel_events')
    op.drop_index(op.f('ix_channel_events_channel'), table_name='channel_events')
    op.drop_table('channel_events')

    op.drop_index(op.f('ix_channel_listings_tenant_id'), table_name='channel_listings')
    op.drop_index(op.f('ix_channel_listings_status'), table_name='channel_listings')
    op.drop_index(op.f('ix_channel_listings_item_id'), table_name='channel_listings')
    op.drop_table('channel_listings')

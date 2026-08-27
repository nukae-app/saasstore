"""tenant features registry replaces configuracio botiga flags

Revision ID: 8ac01b667f42
Revises: 0c06c9e78a72
Create Date: 2026-08-09 17:10:00.000000

Fase 7 (ver docs/ARQUITECTURA_CORE_VERTICAL.md §9/§13): sustituye las
columnas sueltas `ConfiguracioBotiga.discogs_habilitat`/`subscripcions_actives`
por un registro genérico `tenant_features` — un vertical nuevo con su
propio interruptor no debe forzar añadir una columna a `configuracio_botiga`
cada vez.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8ac01b667f42'
down_revision: Union[str, None] = '0c06c9e78a72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tenant_features',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('feature_key', sa.String(length=50), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'feature_key'),
    )
    op.create_index(op.f('ix_tenant_features_tenant_id'), 'tenant_features', ['tenant_id'])
    op.create_index(op.f('ix_tenant_features_feature_key'), 'tenant_features', ['feature_key'])

    # Backfill: una fila por flag existente, solo si estaba activo — un
    # tenant sin fila para una feature se interpreta como "desactivada"
    # (ver ConfiguracioBotiga._feature: None -> False), igual que antes
    # con el default de la columna.
    op.execute("""
        INSERT INTO tenant_features (tenant_id, feature_key, enabled)
        SELECT tenant_id, 'discogs_sync', discogs_habilitat FROM configuracio_botiga
        WHERE discogs_habilitat = true
    """)
    op.execute("""
        INSERT INTO tenant_features (tenant_id, feature_key, enabled)
        SELECT tenant_id, 'subscriptions', subscripcions_actives FROM configuracio_botiga
        WHERE subscripcions_actives = true
    """)

    op.drop_column('configuracio_botiga', 'discogs_habilitat')
    op.drop_column('configuracio_botiga', 'subscripcions_actives')


def downgrade() -> None:
    op.add_column(
        'configuracio_botiga',
        sa.Column('subscripcions_actives', sa.Boolean(), server_default='false', nullable=False),
    )
    op.add_column(
        'configuracio_botiga',
        sa.Column('discogs_habilitat', sa.Boolean(), server_default='false', nullable=False),
    )
    op.execute("""
        UPDATE configuracio_botiga SET discogs_habilitat = true
        WHERE tenant_id IN (SELECT tenant_id FROM tenant_features WHERE feature_key = 'discogs_sync' AND enabled = true)
    """)
    op.execute("""
        UPDATE configuracio_botiga SET subscripcions_actives = true
        WHERE tenant_id IN (SELECT tenant_id FROM tenant_features WHERE feature_key = 'subscriptions' AND enabled = true)
    """)
    op.drop_table('tenant_features')

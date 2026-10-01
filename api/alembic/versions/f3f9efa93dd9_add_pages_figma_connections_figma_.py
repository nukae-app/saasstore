"""add pages, figma_connections, figma_import_jobs

Revision ID: f3f9efa93dd9
Revises: a1b7f4d92e3c
Create Date: 2026-09-27 19:59:56.401724

Fase 1 de docs/ARQUITECTURA_DISENY_FIGMA.md §3 — modelo de datos ya
discutido y aprobado en ese documento. Este fichero se editó a mano a
partir del `alembic revision --autogenerate` real: el autogenerate también
detectó ~60 renombrados de índice preexistentes y no relacionados (nombres
en catalán/castellano que quedaron desincronizados tras el rename de
columnas a inglés de Fase 4 Etapa A — ver ARQUITECTURA_CORE_VERTICAL.md
§16) que se han excluido deliberadamente de aquí para no mezclar deuda
técnica sin relación con esta migración.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3f9efa93dd9'
down_revision: Union[str, None] = 'a1b7f4d92e3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('figma_connections',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('figma_user_id', sa.String(length=100), nullable=False),
    sa.Column('figma_handle', sa.String(length=200), nullable=True),
    sa.Column('connected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id')
    )
    op.create_index(op.f('ix_figma_connections_tenant_id'), 'figma_connections', ['tenant_id'], unique=False)
    op.create_table('pages',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('draft_tree', sa.JSON(), server_default='{}', nullable=False),
    sa.Column('published_tree', sa.JSON(), nullable=True),
    sa.Column('seo_title', sa.JSON(), server_default='{}', nullable=False),
    sa.Column('seo_description', sa.JSON(), server_default='{}', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'slug')
    )
    op.create_index(op.f('ix_pages_slug'), 'pages', ['slug'], unique=False)
    op.create_index(op.f('ix_pages_tenant_id'), 'pages', ['tenant_id'], unique=False)
    op.create_table('figma_import_jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('figma_file_key', sa.String(length=200), nullable=False),
    sa.Column('status', sa.Enum('pending', 'processing', 'ready', 'error', name='figma_import_status'), server_default='pending', nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('raw_snapshot_path', sa.String(length=500), nullable=True),
    sa.Column('result_tree', sa.JSON(), nullable=True),
    sa.Column('target_page_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['target_page_id'], ['pages.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_figma_import_jobs_status'), 'figma_import_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_figma_import_jobs_target_page_id'), 'figma_import_jobs', ['target_page_id'], unique=False)
    op.create_index(op.f('ix_figma_import_jobs_tenant_id'), 'figma_import_jobs', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_figma_import_jobs_tenant_id'), table_name='figma_import_jobs')
    op.drop_index(op.f('ix_figma_import_jobs_target_page_id'), table_name='figma_import_jobs')
    op.drop_index(op.f('ix_figma_import_jobs_status'), table_name='figma_import_jobs')
    op.drop_table('figma_import_jobs')
    op.drop_index(op.f('ix_pages_tenant_id'), table_name='pages')
    op.drop_index(op.f('ix_pages_slug'), table_name='pages')
    op.drop_table('pages')
    op.drop_index(op.f('ix_figma_connections_tenant_id'), table_name='figma_connections')
    op.drop_table('figma_connections')
    op.execute('DROP TYPE figma_import_status')

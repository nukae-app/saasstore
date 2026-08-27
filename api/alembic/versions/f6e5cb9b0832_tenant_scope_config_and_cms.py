"""tenant_scope_config_and_cms

Revision ID: f6e5cb9b0832
Revises: 241bdc35acbf
Create Date: 2026-08-07 07:45:00.000000

Fase 3 (ver plan /Users/paumartinez/.claude/plans/swift-gathering-bengio.md,
sección A): arregla un bug de aislamiento (`marges_config`/`proveedores`
estaban detrás del mismo router admin que el resto de tablas ya aisladas
por tenant, pero sin `tenant_id` — cualquier admin veía/editaba las de
todos los tenants) y escala a tenant las tablas de contenido que hasta
ahora eran globales (`translations`, `pagines`, `posts`, `events`,
`newsletter_campaigns`) — sin esto, un segundo tenant vería y podría
editar el blog/páginas/agenda/newsletters del primero.

Mismo patrón que la migración de Fase 1
(`9ee2df1716bf_multi_tenant_core_tenant_id.py`): columna nullable primero,
backfill al tenant sembrado, luego NOT NULL, más RLS en Postgres como
cinturón extra sobre el filtro de `app/tenancy.py`.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f6e5cb9b0832'
down_revision: Union[str, None] = '241bdc35acbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tablas que ganan `tenant_id` en esta fase (ver Fase 3 en models.py).
SCOPED_TABLES = [
    'events', 'marges_config', 'newsletter_campaigns', 'pagines', 'posts',
    'proveedores', 'translations',
]

DEFAULT_TENANT_ID = uuid.UUID('00000000-0000-0000-0000-000000000001')


def upgrade() -> None:
    bind = op.get_bind()

    # 1. `tenant_id` NULLABLE primero, backfill al tenant existente
    #    (recordstore), y solo entonces NOT NULL.
    for table in SCOPED_TABLES:
        op.add_column(table, sa.Column('tenant_id', sa.Uuid(), nullable=True))
        op.execute(
            sa.text(f"UPDATE {table} SET tenant_id = :tid").bindparams(
                sa.bindparam("tid", value=DEFAULT_TENANT_ID, type_=sa.Uuid())
            )
        )
        op.alter_column(table, 'tenant_id', nullable=False)
        op.create_index(op.f(f'ix_{table}_tenant_id'), table, ['tenant_id'], unique=False)
        op.create_foreign_key(None, table, 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # 2. UNIQUE simples -> compuestas (tenant_id, X), mismo patrón que
    #    etiquetes/seccions en la Fase 1.
    # A diferencia de `translations` (UniqueConstraint explícita en
    # __table_args__), `proveedores.nombre`/`pagines.slug`/`posts.slug`
    # usaban `unique=True, index=True` a nivel de columna — Postgres lo
    # implementa como un único índice UNIQUE, sin constraint con nombre
    # aparte que haga falta soltar primero.
    op.drop_index('ix_proveedores_nombre', table_name='proveedores')
    op.create_index(op.f('ix_proveedores_nombre'), 'proveedores', ['nombre'], unique=False)
    op.create_unique_constraint(None, 'proveedores', ['tenant_id', 'nombre'])

    op.drop_constraint('translations_key_lang_key', 'translations', type_='unique')
    op.create_unique_constraint(None, 'translations', ['tenant_id', 'key', 'lang'])

    op.drop_index('ix_pagines_slug', table_name='pagines')
    op.create_index(op.f('ix_pagines_slug'), 'pagines', ['slug'], unique=False)
    op.create_unique_constraint(None, 'pagines', ['tenant_id', 'slug'])

    op.drop_index('ix_posts_slug', table_name='posts')
    op.create_index(op.f('ix_posts_slug'), 'posts', ['slug'], unique=False)
    op.create_unique_constraint(None, 'posts', ['tenant_id', 'slug'])

    # 3. RLS en Postgres — mismo cinturón extra que la Fase 1 (SQLite, usado
    #    en tests, no lo soporta y se salta esta parte sin más).
    if bind.dialect.name == 'postgresql':
        for table in SCOPED_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} "
                f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        for table in SCOPED_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_constraint(None, 'posts', type_='unique')
    op.drop_index(op.f('ix_posts_slug'), table_name='posts')
    op.create_index('ix_posts_slug', 'posts', ['slug'], unique=True)
    op.drop_constraint(None, 'posts', type_='foreignkey')
    op.drop_index(op.f('ix_posts_tenant_id'), table_name='posts')
    op.drop_column('posts', 'tenant_id')

    op.drop_constraint(None, 'pagines', type_='unique')
    op.drop_index(op.f('ix_pagines_slug'), table_name='pagines')
    op.create_index('ix_pagines_slug', 'pagines', ['slug'], unique=True)
    op.drop_constraint(None, 'pagines', type_='foreignkey')
    op.drop_index(op.f('ix_pagines_tenant_id'), table_name='pagines')
    op.drop_column('pagines', 'tenant_id')

    op.drop_constraint(None, 'translations', type_='unique')
    op.create_unique_constraint('translations_key_lang_key', 'translations', ['key', 'lang'])
    op.drop_constraint(None, 'translations', type_='foreignkey')
    op.drop_index(op.f('ix_translations_tenant_id'), table_name='translations')
    op.drop_column('translations', 'tenant_id')

    op.drop_constraint(None, 'proveedores', type_='unique')
    op.drop_index(op.f('ix_proveedores_nombre'), table_name='proveedores')
    op.create_index('ix_proveedores_nombre', 'proveedores', ['nombre'], unique=True)
    op.drop_constraint(None, 'proveedores', type_='foreignkey')
    op.drop_index(op.f('ix_proveedores_tenant_id'), table_name='proveedores')
    op.drop_column('proveedores', 'tenant_id')

    op.drop_constraint(None, 'newsletter_campaigns', type_='foreignkey')
    op.drop_index(op.f('ix_newsletter_campaigns_tenant_id'), table_name='newsletter_campaigns')
    op.drop_column('newsletter_campaigns', 'tenant_id')

    op.drop_constraint(None, 'marges_config', type_='foreignkey')
    op.drop_index(op.f('ix_marges_config_tenant_id'), table_name='marges_config')
    op.drop_column('marges_config', 'tenant_id')

    op.drop_constraint(None, 'events', type_='foreignkey')
    op.drop_index(op.f('ix_events_tenant_id'), table_name='events')
    op.drop_column('events', 'tenant_id')

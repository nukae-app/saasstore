"""multi_tenant_core_tenant_id

Revision ID: 9ee2df1716bf
Revises: c7e4b1a9d3f8
Create Date: 2026-08-06 20:59:20.639663

Fase 1 del núcleo multi-tenant (ver plan
/Users/paumartinez/.claude/plans/swift-gathering-bengio.md): crea `tenants`,
añade `tenant_id` a las 21 tablas tocadas en la ruta catálogo→carrito→
checkout→pago→pedido, convierte las UNIQUE afectadas en compuestas
`(tenant_id, X)`, siembra un tenant por defecto (dominio `testserver`, para
que tests y dev local funcionen sin configurar nada) con su fila de
`configuracio_botiga`, y activa Row-Level Security en Postgres como cinturón
de seguridad extra sobre el filtro de aplicación (`app/tenancy.py`) — SQLite
no lo soporta, así que esa parte se salta ahí sin más.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '9ee2df1716bf'
down_revision: Union[str, None] = 'c7e4b1a9d3f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tablas que ganan `tenant_id` en esta fase (ver TenantScoped en models.py).
SCOPED_TABLES = [
    'addresses', 'auth_tokens', 'cart_items', 'carts', 'configuracio_botiga',
    'etiquetes', 'identities', 'items', 'order_items', 'orders', 'payments',
    'pes_format', 'refresh_tokens', 'release_etiquetes', 'release_images',
    'releases', 'seccions', 'stock_holds', 'tipus_iva', 'trams_enviament', 'users',
]

DEFAULT_TENANT_ID = uuid.UUID('00000000-0000-0000-0000-000000000001')


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Tabla de tenants + siembra del tenant por defecto.
    op.create_table(
        'tenants',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('slug', sa.String(length=60), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tenants_activo'), 'tenants', ['activo'], unique=False)
    op.create_index(op.f('ix_tenants_domain'), 'tenants', ['domain'], unique=True)
    op.create_index(op.f('ix_tenants_slug'), 'tenants', ['slug'], unique=True)

    tenants_table = sa.table(
        'tenants',
        sa.column('id', sa.Uuid()),
        sa.column('slug', sa.String()),
        sa.column('domain', sa.String()),
        sa.column('nombre', sa.String()),
        sa.column('activo', sa.Boolean()),
    )
    op.bulk_insert(tenants_table, [{
        'id': DEFAULT_TENANT_ID,
        'slug': 'recordstore',
        # 'testserver' para que TestClient(app, base_url="https://testserver")
        # y conftest.py resuelvan tenant sin configurar nada (ver
        # tests/conftest.py). En un despliegue real, cambiar el dominio desde
        # la tabla `tenants` sin tocar código.
        'domain': 'testserver',
        'nombre': 'Ultra-Local Records',
        'activo': True,
    }])

    # 2. `tenant_id` NULLABLE primero, backfill al tenant sembrado, y solo
    #    entonces NOT NULL — así la migración es segura aunque estas tablas
    #    ya tuvieran filas (no es el caso en un proyecto nuevo, pero es la
    #    forma correcta de añadir una columna NOT NULL).
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

    # 3. UNIQUE simples -> compuestas (tenant_id, X).
    op.drop_constraint('etiquetes_slug_key', 'etiquetes', type_='unique')
    op.drop_index('ix_etiquetes_slug', table_name='etiquetes')
    op.create_index(op.f('ix_etiquetes_slug'), 'etiquetes', ['slug'], unique=False)
    op.create_unique_constraint(None, 'etiquetes', ['tenant_id', 'slug'])

    op.drop_constraint('seccions_slug_key', 'seccions', type_='unique')
    op.drop_index('ix_seccions_slug', table_name='seccions')
    op.create_index(op.f('ix_seccions_slug'), 'seccions', ['slug'], unique=False)
    op.create_unique_constraint(None, 'seccions', ['tenant_id', 'slug'])

    op.drop_constraint('items_codi_discogs_key', 'items', type_='unique')
    op.create_unique_constraint(None, 'items', ['tenant_id', 'codi_discogs'])

    op.drop_constraint('pes_format_formato_key', 'pes_format', type_='unique')
    op.create_unique_constraint(None, 'pes_format', ['tenant_id', 'formato'])

    op.drop_constraint('identities_provider_provider_user_id_key', 'identities', type_='unique')
    op.create_unique_constraint(None, 'identities', ['tenant_id', 'provider', 'provider_user_id'])

    op.drop_index('ix_users_email', table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_unique_constraint(None, 'users', ['tenant_id', 'email'])

    op.create_unique_constraint(None, 'configuracio_botiga', ['tenant_id'])

    # 4. `configuracio_botiga` deja de ser una fila fija id=1 (ver
    #    models.py::ConfiguracioBotiga). La fila id=1 ya existe (la sembró la
    #    migración a552e477bc7b) y el bucle del punto 2 ya le pone
    #    `tenant_id` igual que a cualquier otra fila de esta tabla — no hace
    #    falta insertar nada aquí. Lo que sí falta es que `id` tenga
    #    secuencia propia en Postgres (nunca la tuvo: la app siempre fijaba
    #    1 a mano), para que un tenant futuro pueda tener su propia fila sin
    #    especificar `id` a mano.
    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TABLE configuracio_botiga ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY")
        op.execute(
            "SELECT setval(pg_get_serial_sequence('configuracio_botiga', 'id'), "
            "COALESCE((SELECT MAX(id) FROM configuracio_botiga), 1))"
        )

    # 5. RLS en Postgres — cinturón de seguridad extra sobre el filtro de
    #    aplicación (app/tenancy.py::_filter_by_tenant), no el mecanismo
    #    principal (los tests corren en SQLite y no pueden ejercitar esto).
    #    FORCE ROW LEVEL SECURITY hace falta porque, por defecto, RLS no se
    #    aplica al propietario de la tabla — y la conexión de la API suele
    #    ser ese mismo usuario.
    if bind.dialect.name == 'postgresql':
        for table in SCOPED_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            # NULLIF(...) convierte '' a NULL antes del cast: current_setting
            # con missing_ok=true puede devolver '' en vez de NULL según cómo
            # haya quedado la sesión (p.ej. tras un RESET) — sin NULLIF, eso
            # revienta con un error de casteo en vez de fallar limpiamente a
            # cero filas (fail-closed real, no un 500).
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

    op.drop_constraint(None, 'users', type_='foreignkey')
    op.drop_constraint(None, 'users', type_='unique')
    op.drop_index(op.f('ix_users_tenant_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.drop_column('users', 'tenant_id')
    op.drop_constraint(None, 'trams_enviament', type_='foreignkey')
    op.drop_index(op.f('ix_trams_enviament_tenant_id'), table_name='trams_enviament')
    op.drop_column('trams_enviament', 'tenant_id')
    op.drop_constraint(None, 'tipus_iva', type_='foreignkey')
    op.drop_index(op.f('ix_tipus_iva_tenant_id'), table_name='tipus_iva')
    op.drop_column('tipus_iva', 'tenant_id')
    op.drop_constraint(None, 'stock_holds', type_='foreignkey')
    op.drop_index(op.f('ix_stock_holds_tenant_id'), table_name='stock_holds')
    op.drop_column('stock_holds', 'tenant_id')
    op.drop_constraint(None, 'seccions', type_='foreignkey')
    op.drop_constraint(None, 'seccions', type_='unique')
    op.drop_index(op.f('ix_seccions_tenant_id'), table_name='seccions')
    op.drop_index(op.f('ix_seccions_slug'), table_name='seccions')
    op.create_index('ix_seccions_slug', 'seccions', ['slug'], unique=True)
    op.create_unique_constraint('seccions_slug_key', 'seccions', ['slug'])
    op.drop_column('seccions', 'tenant_id')
    op.drop_constraint(None, 'releases', type_='foreignkey')
    op.drop_index(op.f('ix_releases_tenant_id'), table_name='releases')
    op.drop_column('releases', 'tenant_id')
    op.drop_constraint(None, 'release_images', type_='foreignkey')
    op.drop_index(op.f('ix_release_images_tenant_id'), table_name='release_images')
    op.drop_column('release_images', 'tenant_id')
    op.drop_constraint(None, 'release_etiquetes', type_='foreignkey')
    op.drop_index(op.f('ix_release_etiquetes_tenant_id'), table_name='release_etiquetes')
    op.drop_column('release_etiquetes', 'tenant_id')
    op.drop_constraint(None, 'refresh_tokens', type_='foreignkey')
    op.drop_index(op.f('ix_refresh_tokens_tenant_id'), table_name='refresh_tokens')
    op.drop_column('refresh_tokens', 'tenant_id')
    op.drop_constraint(None, 'pes_format', type_='foreignkey')
    op.drop_constraint(None, 'pes_format', type_='unique')
    op.drop_index(op.f('ix_pes_format_tenant_id'), table_name='pes_format')
    op.create_unique_constraint('pes_format_formato_key', 'pes_format', ['formato'])
    op.drop_column('pes_format', 'tenant_id')
    op.drop_constraint(None, 'payments', type_='foreignkey')
    op.drop_index(op.f('ix_payments_tenant_id'), table_name='payments')
    op.drop_column('payments', 'tenant_id')
    op.drop_constraint(None, 'orders', type_='foreignkey')
    op.drop_index(op.f('ix_orders_tenant_id'), table_name='orders')
    op.drop_column('orders', 'tenant_id')
    op.drop_constraint(None, 'order_items', type_='foreignkey')
    op.drop_index(op.f('ix_order_items_tenant_id'), table_name='order_items')
    op.drop_column('order_items', 'tenant_id')
    op.drop_constraint(None, 'items', type_='foreignkey')
    op.drop_constraint(None, 'items', type_='unique')
    op.drop_index(op.f('ix_items_tenant_id'), table_name='items')
    op.create_unique_constraint('items_codi_discogs_key', 'items', ['codi_discogs'])
    op.drop_column('items', 'tenant_id')
    op.drop_constraint(None, 'identities', type_='foreignkey')
    op.drop_constraint(None, 'identities', type_='unique')
    op.drop_index(op.f('ix_identities_tenant_id'), table_name='identities')
    op.create_unique_constraint('identities_provider_provider_user_id_key', 'identities', ['provider', 'provider_user_id'])
    op.drop_column('identities', 'tenant_id')
    op.drop_constraint(None, 'etiquetes', type_='foreignkey')
    op.drop_constraint(None, 'etiquetes', type_='unique')
    op.drop_index(op.f('ix_etiquetes_tenant_id'), table_name='etiquetes')
    op.drop_index(op.f('ix_etiquetes_slug'), table_name='etiquetes')
    op.create_index('ix_etiquetes_slug', 'etiquetes', ['slug'], unique=True)
    op.create_unique_constraint('etiquetes_slug_key', 'etiquetes', ['slug'])
    op.drop_column('etiquetes', 'tenant_id')
    op.drop_constraint(None, 'configuracio_botiga', type_='foreignkey')
    op.drop_constraint(None, 'configuracio_botiga', type_='unique')
    op.drop_index(op.f('ix_configuracio_botiga_tenant_id'), table_name='configuracio_botiga')
    op.drop_column('configuracio_botiga', 'tenant_id')
    op.drop_constraint(None, 'carts', type_='foreignkey')
    op.drop_index(op.f('ix_carts_tenant_id'), table_name='carts')
    op.drop_column('carts', 'tenant_id')
    op.drop_constraint(None, 'cart_items', type_='foreignkey')
    op.drop_index(op.f('ix_cart_items_tenant_id'), table_name='cart_items')
    op.drop_column('cart_items', 'tenant_id')
    op.drop_constraint(None, 'auth_tokens', type_='foreignkey')
    op.drop_index(op.f('ix_auth_tokens_tenant_id'), table_name='auth_tokens')
    op.drop_column('auth_tokens', 'tenant_id')
    op.drop_constraint(None, 'addresses', type_='foreignkey')
    op.drop_index(op.f('ix_addresses_tenant_id'), table_name='addresses')
    op.drop_column('addresses', 'tenant_id')
    op.drop_index(op.f('ix_tenants_slug'), table_name='tenants')
    op.drop_index(op.f('ix_tenants_domain'), table_name='tenants')
    op.drop_index(op.f('ix_tenants_activo'), table_name='tenants')
    op.drop_table('tenants')

"""tenant_scope_erp_club

Revision ID: d49fb8ad7897
Revises: 9f3ecef4ae50
Create Date: 2026-08-07 09:00:00.000000

Fase 4 (ver plan /Users/paumartinez/.claude/plans/swift-gathering-bengio.md,
sección A): arregla un bug de aislamiento más grande que el de la Fase 3 —
24 tablas de ERP, contabilidad y club de suscripción nunca se aislaron por
tenant, ni en la Fase 1 ni después. Hoy todos los tenants comparten un
único pool global de compras, gastos, cuentas bancarias, sesiones de caja
y datos del club de disc.

Mismo patrón que las dos migraciones anteriores
(`9ee2df1716bf_multi_tenant_core_tenant_id.py`,
`f6e5cb9b0832_tenant_scope_config_and_cms.py`): columna nullable primero,
backfill al tenant existente, luego NOT NULL, más RLS en Postgres.

`configuracio_subscripcio` recibe además el mismo arreglo que
`configuracio_botiga` tuvo en la Fase 1: deja de depender de una fila fija
(aunque aquí `id` ya usaba una secuencia real, a diferencia de
`configuracio_botiga` en su día, así que no hace falta tocar `id`) — solo
se añade `UNIQUE (tenant_id)` para que sea la clave natural por tenant.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd49fb8ad7897'
down_revision: Union[str, None] = '9f3ecef4ae50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tablas que ganan `tenant_id` en esta fase (ver Fase 4 en models.py).
SCOPED_TABLES = [
    'caixa_diaria', 'caja_movimientos', 'caja_sessions', 'cobraments_subscripcio',
    'comanda_items', 'comandas', 'compras', 'comptes_bancaris', 'configuracio_subscripcio',
    'despeses', 'devolucions_compra', 'devolucions_venta', 'historial_compres',
    'moviments_bancaris', 'newsletter_sends', 'periodes_comptables', 'peticiones_cliente',
    'posts_pagines', 'solicitud_compra_items', 'solicitudes_compra', 'spotify_connections',
    'subscripcio_assignacions', 'subscripcions', 'ventas_externas',
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

    # 2. UNIQUE simples -> compuestas (tenant_id, X). `comandas.num_comanda`
    #    y `caixa_diaria.data` eran índices únicos (unique=True a nivel de
    #    columna); `periodes_comptables` era una UniqueConstraint con
    #    nombre propio (__table_args__) — cada uno se trata según lo que
    #    realmente existe en Postgres, no por igual.
    op.drop_index('ix_comandas_num_comanda', table_name='comandas')
    op.create_index(op.f('ix_comandas_num_comanda'), 'comandas', ['num_comanda'], unique=False)
    op.create_unique_constraint(None, 'comandas', ['tenant_id', 'num_comanda'])

    op.drop_index('ix_caixa_diaria_data', table_name='caixa_diaria')
    op.create_index(op.f('ix_caixa_diaria_data'), 'caixa_diaria', ['data'], unique=False)
    op.create_unique_constraint(None, 'caixa_diaria', ['tenant_id', 'data'])

    op.drop_constraint('periodes_comptables_year_mes_key', 'periodes_comptables', type_='unique')
    op.create_unique_constraint(None, 'periodes_comptables', ['tenant_id', 'year', 'mes'])

    # 3. `configuracio_subscripcio`: clave natural por tenant, mismo criterio
    #    que `configuracio_botiga` en la Fase 1 — `id` ya usaba secuencia
    #    real en Postgres (a diferencia de `configuracio_botiga` en su día),
    #    así que no hace falta tocarlo, solo añadir la UNIQUE.
    op.create_unique_constraint(None, 'configuracio_subscripcio', ['tenant_id'])

    # Nota: `cobraments_subscripcio_ds_order_key` (UNIQUE en `ds_order`) se
    # deja intacta a propósito — Ds_Merchant_Order de Redsys es un
    # identificador global por diseño, mismo criterio que `Payment.ds_order`
    # desde la Fase 1 (drift ya documentado en migraciones anteriores,
    # autogenerate lo vuelve a proponer soltar cada vez, se descarta aquí
    # también). `spotify_connections.spotify_user_id` (UNIQUE) se deja
    # igual, mismo criterio (identificador OAuth externo).

    # 4. RLS en Postgres.
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

    op.drop_constraint('configuracio_subscripcio_tenant_id_key', 'configuracio_subscripcio', type_='unique')

    op.drop_constraint('periodes_comptables_tenant_id_year_mes_key', 'periodes_comptables', type_='unique')
    op.create_unique_constraint('periodes_comptables_year_mes_key', 'periodes_comptables', ['year', 'mes'])

    op.drop_constraint('caixa_diaria_tenant_id_data_key', 'caixa_diaria', type_='unique')
    op.drop_index(op.f('ix_caixa_diaria_data'), table_name='caixa_diaria')
    op.create_index('ix_caixa_diaria_data', 'caixa_diaria', ['data'], unique=True)

    op.drop_constraint('comandas_tenant_id_num_comanda_key', 'comandas', type_='unique')
    op.drop_index(op.f('ix_comandas_num_comanda'), table_name='comandas')
    op.create_index('ix_comandas_num_comanda', 'comandas', ['num_comanda'], unique=True)

    for table in reversed(SCOPED_TABLES):
        op.drop_constraint(f'{table}_tenant_id_fkey', table, type_='foreignkey')
        op.drop_index(op.f(f'ix_{table}_tenant_id'), table_name=table)
        op.drop_column(table, 'tenant_id')

"""stock agregado para discos nuevos

Revision ID: 4e64f56931ca
Revises: 043c77e179f3
Create Date: 2026-08-03 00:00:00.000000

Escrita a mano (sin `alembic revision --autogenerate`: no había red directa
desde el puesto de desarrollo hacia el RDS de producción). Aditiva y
retrocompatible: todas las columnas nuevas llevan server_default, así que el
código ya desplegado (que no las conoce) sigue funcionando exactamente igual
tras aplicarla.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '4e64f56931ca'
down_revision: Union[str, None] = '043c77e179f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONDICION_ITEM = postgresql.ENUM('nou', 'segona_ma', name='condicion_item', create_type=False)


def upgrade() -> None:
    # --- compras: coste total de la recepción, ya no derivable de forma
    # fiable de Item.compra_id una vez una línea nou puede acumular varias
    # recepciones (ver comentario en el modelo Compra) ----------------------
    op.add_column('compras', sa.Column('coste_total', sa.Numeric(10, 2), nullable=True))
    op.execute(
        "UPDATE compras c SET coste_total = sub.total FROM ("
        "  SELECT compra_id, SUM(coste_adquisicion) AS total FROM items "
        "  WHERE compra_id IS NOT NULL GROUP BY compra_id"
        ") sub WHERE sub.compra_id = c.id"
    )

    # --- items: cantidad agregada (solo se usa para condicion='nou') -------
    op.add_column('items', sa.Column('cantidad', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('items', sa.Column('cantidad_reservada', sa.Integer(), nullable=False, server_default='0'))
    op.create_check_constraint('ck_items_cantidad_no_negativa', 'items', 'cantidad >= 0')
    op.create_check_constraint(
        'ck_items_cantidad_reservada_valida', 'items',
        'cantidad_reservada >= 0 AND cantidad_reservada <= cantidad',
    )

    # --- cart_items: cantidad deseada por línea (nou) -----------------------
    op.add_column('cart_items', sa.Column('cantidad', sa.Integer(), nullable=False, server_default='1'))

    # --- order_items: cantidad + snapshot de condicion ----------------------
    op.add_column('order_items', sa.Column('cantidad', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('order_items', sa.Column('condicion', _CONDICION_ITEM, nullable=True))
    op.execute(
        "UPDATE order_items oi SET condicion = i.condicion "
        "FROM items i WHERE oi.item_id = i.id AND oi.condicion IS NULL"
    )
    # La UNIQUE original ('una copia se vende una vez') se sustituye por un
    # índice único PARCIAL solo sobre condicion='segona_ma': una línea `nou`
    # (stock agregado) puede aparecer en varios OrderItem a lo largo del
    # tiempo. Nombre de la constraint original: la que crea Postgres por
    # defecto para `UniqueConstraint('item_id')` sin nombre explícito en el
    # create_table original (ver ab4340a7ea5a_initial_schema.py). Si el
    # nombre real difiere (comprobar con `\d order_items` antes de aplicar),
    # ajustar esta línea.
    op.drop_constraint('order_items_item_id_key', 'order_items', type_='unique')
    op.create_index(
        'ix_order_items_item_id_unico_segona_ma', 'order_items', ['item_id'],
        unique=True, postgresql_where=sa.text("condicion = 'segona_ma'"),
    )

    # --- ventas_externas: mismo tratamiento que order_items -----------------
    op.add_column('ventas_externas', sa.Column('cantidad', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('ventas_externas', sa.Column('condicion', _CONDICION_ITEM, nullable=True))
    op.execute(
        "UPDATE ventas_externas ve SET condicion = i.condicion "
        "FROM items i WHERE ve.item_id = i.id AND ve.condicion IS NULL"
    )
    op.drop_constraint('ventas_externas_item_id_key', 'ventas_externas', type_='unique')
    op.create_index(
        'ix_ventas_externas_item_id_unico_segona_ma', 'ventas_externas', ['item_id'],
        unique=True, postgresql_where=sa.text("condicion = 'segona_ma'"),
    )

    # --- devoluciones: cuántas unidades se devuelven ------------------------
    op.add_column('devolucions_venta', sa.Column('cantidad', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('devolucions_compra', sa.Column('cantidad', sa.Integer(), nullable=False, server_default='1'))

    # --- stock_holds: retenciones de stock agregado (solo nou) --------------
    op.create_table(
        'stock_holds',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('item_id', sa.Uuid(), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False),
        sa.Column('cart_id', sa.Uuid(), nullable=True),
        sa.Column('peticion_id', sa.Uuid(), nullable=True),
        sa.Column('assignacio_id', sa.Uuid(), nullable=True),
        sa.Column('order_id', sa.Uuid(), nullable=True),
        sa.Column('reserved_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cart_id'], ['carts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['peticion_id'], ['peticiones_cliente.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assignacio_id'], ['subscripcio_assignacions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_stock_holds_item_id'), 'stock_holds', ['item_id'], unique=False)
    op.create_index(op.f('ix_stock_holds_cart_id'), 'stock_holds', ['cart_id'], unique=False)
    op.create_index(op.f('ix_stock_holds_peticion_id'), 'stock_holds', ['peticion_id'], unique=False)
    op.create_index(op.f('ix_stock_holds_assignacio_id'), 'stock_holds', ['assignacio_id'], unique=False)
    op.create_index(op.f('ix_stock_holds_order_id'), 'stock_holds', ['order_id'], unique=False)


def downgrade() -> None:
    op.drop_table('stock_holds')

    op.drop_column('compras', 'coste_total')

    op.drop_column('devolucions_compra', 'cantidad')
    op.drop_column('devolucions_venta', 'cantidad')

    op.drop_index('ix_ventas_externas_item_id_unico_segona_ma', table_name='ventas_externas')
    op.create_unique_constraint('ventas_externas_item_id_key', 'ventas_externas', ['item_id'])
    op.drop_column('ventas_externas', 'condicion')
    op.drop_column('ventas_externas', 'cantidad')

    op.drop_index('ix_order_items_item_id_unico_segona_ma', table_name='order_items')
    op.create_unique_constraint('order_items_item_id_key', 'order_items', ['item_id'])
    op.drop_column('order_items', 'condicion')
    op.drop_column('order_items', 'cantidad')

    op.drop_column('cart_items', 'cantidad')

    op.drop_constraint('ck_items_cantidad_reservada_valida', 'items', type_='check')
    op.drop_constraint('ck_items_cantidad_no_negativa', 'items', type_='check')
    op.drop_column('items', 'cantidad_reservada')
    op.drop_column('items', 'cantidad')

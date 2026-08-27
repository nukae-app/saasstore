"""fase 4 etapa a: rename columns to english (batch 3: items, order_items, ventas_externas)

Revision ID: b45384f7d18d
Revises: 99ad9189db2a
Create Date: 2026-08-25 02:00:00.000000

Fase 4 Etapa A (ver docs/ARQUITECTURA_CORE_VERTICAL.md §6/§14/§16): último
batch del rename DB-only de columnas Core a inglés, sobre las tres tablas
que se dejaron fuera de los batches anteriores por tener SQL en crudo que
referencia nombres de columna como texto (CheckConstraints e índices
parciales) — ver CLAUDE.md: la reserva atómica de stock sobre `items` es
"la pieza más delicada" del sistema.

Además de los `ALTER TABLE ... RENAME COLUMN`, esta migración:
- Recrea los dos CheckConstraint de `items` (`cantidad`/`cantidad_reservada`
  -> `quantity`/`reserved_quantity`) con la condición SQL actualizada.
- Recrea los índices únicos parciales de `order_items` y `ventas_externas`
  (`ix_order_items_item_id_unico_segona_ma`,
  `ix_ventas_externas_item_id_unico_segona_ma`) con la cláusula WHERE
  actualizada (`condicion` -> `condition`).

Igual que en los batches anteriores: el atributo Python del modelo no
cambia (mapped_column("nombre_ingles")), así que schemas.py, routers,
services (incluido services/reservations.py, que usa expresiones ORM tipo
`Item.cantidad_reservada`, no SQL en crudo) y frontend no se tocan.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = 'b45384f7d18d'
down_revision: Union[str, None] = '99ad9189db2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RENAMES: list[tuple[str, str, str]] = [
    # items
    ("items", "precio", "price"),
    ("items", "condicion", "condition"),
    ("items", "cantidad", "quantity"),
    ("items", "cantidad_reservada", "reserved_quantity"),
    ("items", "fecha_entrada", "entry_date"),
    ("items", "subscripcio_pool", "subscription_pool"),
    ("items", "coste_adquisicion", "acquisition_cost"),
    # order_items
    ("order_items", "precio", "price"),
    ("order_items", "condicion", "condition"),
    ("order_items", "cantidad", "quantity"),
    ("order_items", "iva_pct", "vat_pct"),
    ("order_items", "iva_import", "vat_amount"),
    # ventas_externas
    ("ventas_externas", "condicion", "condition"),
    ("ventas_externas", "cantidad", "quantity"),
    ("ventas_externas", "descripcion", "description"),
    ("ventas_externas", "canal", "channel"),
    ("ventas_externas", "metodo_pago", "payment_method"),
    ("ventas_externas", "precio_venta", "sale_price"),
    ("ventas_externas", "fecha", "date"),
    ("ventas_externas", "nombre_cliente", "client_name"),
    ("ventas_externas", "notas", "notes"),
    ("ventas_externas", "cobrat_at", "paid_at"),
    ("ventas_externas", "iva_pct", "vat_pct"),
    ("ventas_externas", "iva_import", "vat_amount"),
]


def upgrade() -> None:
    # Los CheckConstraint/Index con SQL en crudo hay que soltarlos ANTES de
    # renombrar (referencian el nombre viejo) y recrearlos DESPUÉS (con el
    # nombre nuevo) — si no, el RENAME COLUMN fallaría porque Postgres no
    # deja renombrar una columna que todavía tiene una constraint/índice
    # apuntándola por nombre en una expresión.
    op.drop_constraint("ck_items_cantidad_no_negativa", "items", type_="check")
    op.drop_constraint("ck_items_cantidad_reservada_valida", "items", type_="check")
    op.drop_index("ix_order_items_item_id_unico_segona_ma", table_name="order_items")
    op.drop_index("ix_ventas_externas_item_id_unico_segona_ma", table_name="ventas_externas")

    for table, old, new in RENAMES:
        op.alter_column(table, old, new_column_name=new)

    op.create_check_constraint("ck_items_cantidad_no_negativa", "items", "quantity >= 0")
    op.create_check_constraint(
        "ck_items_cantidad_reservada_valida", "items",
        "reserved_quantity >= 0 AND reserved_quantity <= quantity",
    )
    op.create_index(
        "ix_order_items_item_id_unico_segona_ma", "order_items", ["item_id"],
        unique=True, postgresql_where=text("condition = 'segona_ma'"),
    )
    op.create_index(
        "ix_ventas_externas_item_id_unico_segona_ma", "ventas_externas", ["item_id"],
        unique=True, postgresql_where=text("condition = 'segona_ma'"),
    )


def downgrade() -> None:
    op.drop_index("ix_ventas_externas_item_id_unico_segona_ma", table_name="ventas_externas")
    op.drop_index("ix_order_items_item_id_unico_segona_ma", table_name="order_items")
    op.drop_constraint("ck_items_cantidad_reservada_valida", "items", type_="check")
    op.drop_constraint("ck_items_cantidad_no_negativa", "items", type_="check")

    for table, old, new in reversed(RENAMES):
        op.alter_column(table, new, new_column_name=old)

    op.create_check_constraint("ck_items_cantidad_no_negativa", "items", "cantidad >= 0")
    op.create_check_constraint(
        "ck_items_cantidad_reservada_valida", "items",
        "cantidad_reservada >= 0 AND cantidad_reservada <= cantidad",
    )
    op.create_index(
        "ix_order_items_item_id_unico_segona_ma", "order_items", ["item_id"],
        unique=True, postgresql_where=text("condicion = 'segona_ma'"),
    )
    op.create_index(
        "ix_ventas_externas_item_id_unico_segona_ma", "ventas_externas", ["item_id"],
        unique=True, postgresql_where=text("condicion = 'segona_ma'"),
    )

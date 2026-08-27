"""fase 4 etapa a: rename columns to english (batch 2: core tables)

Revision ID: 99ad9189db2a
Revises: 7c5f2b01749b
Create Date: 2026-08-25 01:00:00.000000

Fase 4 Etapa A (ver docs/ARQUITECTURA_CORE_VERTICAL.md §6/§14/§16): continúa
el rename DB-only de columnas a inglés vía `ALTER TABLE ... RENAME COLUMN`
sobre el resto de tablas Core (auth, direcciones, catálogo genérico,
carrito, pedidos, ERP de compras/ventas externas, comptabilidad, CMS y
newsletter). Igual que el piloto: solo cambia el nombre de columna en
Postgres, el atributo Python del modelo se queda igual
(mapped_column("nombre_ingles")) — schemas.py, routers, servicios y
frontend no se tocan, el contrato JSON de la API es idéntico.

Se excluyen deliberadamente de este batch: `items`, `order_items` y
`ventas_externas` (tienen CheckConstraints/índices parciales con SQL en
crudo que referencian nombres de columna como texto — ver Item.__table_args__
y los índices `ix_order_items_item_id_unico_segona_ma` /
`ix_ventas_externas_item_id_unico_segona_ma`, que además hay que actualizar
a la vez que se renombra `condicion`). Esas tres tablas se abordan en una
migración aparte, con más cuidado, por ser "la pieza más delicada" del
sistema (reserva atómica de stock).

También se excluyen las tablas de extensión de vertical (`release_records`,
`release_floristeria`, `record_stock_details`, `spotify_connections`,
`pes_format`, y toda la familia de "club del disc":
`configuracio_subscripcio`, `subscripcions`, `cobraments_subscripcio`,
`subscripcio_assignacions`) — Fase 4 Etapa A es solo Core, no Vertical.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '99ad9189db2a'
down_revision: Union[str, None] = '7c5f2b01749b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabla, columna_antigua, columna_nueva)
RENAMES: list[tuple[str, str, str]] = [
    # users
    ("users", "nombre", "name"),
    ("users", "telefon", "phone"),
    ("users", "rol", "role"),
    ("users", "activo", "active"),
    ("users", "idioma", "language"),
    ("users", "notas_internes", "internal_notes"),
    # addresses
    ("addresses", "nombre_destinatario", "recipient_name"),
    ("addresses", "linea1", "address_line1"),
    ("addresses", "linea2", "address_line2"),
    ("addresses", "ciudad", "city"),
    ("addresses", "cp", "postal_code"),
    ("addresses", "provincia", "province"),
    ("addresses", "pais", "country"),
    ("addresses", "telefono", "phone"),
    ("addresses", "predeterminada", "is_default"),
    # releases (solo campos core; artista/sello/etc. viven en release_records, vertical)
    ("releases", "titulo", "title"),
    ("releases", "descripcion", "description"),
    ("releases", "imagen_url", "image_url"),
    ("releases", "pes_g", "weight_g"),
    ("releases", "properament", "coming_soon"),
    ("releases", "data_disponibilitat", "available_at"),
    # release_images
    ("release_images", "posicio", "position"),
    ("release_images", "tipus", "type"),
    ("release_images", "font", "source"),
    # cart_items
    ("cart_items", "cantidad", "quantity"),
    # orders
    ("orders", "email_contacto", "contact_email"),
    ("orders", "coste_envio", "shipping_cost"),
    ("orders", "metodo_envio", "shipping_method"),
    ("orders", "metodo_pago", "payment_method"),
    ("orders", "direccion_envio", "shipping_address"),
    ("orders", "notas", "notes"),
    ("orders", "idioma", "language"),
    ("orders", "cobrat_at", "paid_at"),
    ("orders", "numero_seguiment", "tracking_number"),
    ("orders", "transportista", "carrier"),
    ("orders", "avisada_recollida_at", "pickup_notified_at"),
    ("orders", "origen", "origin"),
    # payments
    ("payments", "proveedor", "provider"),
    ("payments", "importe", "amount"),
    ("payments", "moneda", "currency"),
    ("payments", "estado", "status"),
    # proveedores
    ("proveedores", "nombre", "name"),
    ("proveedores", "tipo", "type"),
    ("proveedores", "telefon", "phone"),
    ("proveedores", "direccion", "address"),
    ("proveedores", "contacto", "contact"),
    ("proveedores", "actiu", "active"),
    ("proveedores", "iban_proveidor", "supplier_iban"),
    ("proveedores", "metode_pagament", "payment_method"),
    ("proveedores", "dies_pagament", "payment_days"),
    ("proveedores", "dia_pagament_mes", "payment_day_of_month"),
    ("proveedores", "notas", "notes"),
    # compras
    ("compras", "nombre_particular", "individual_name"),
    ("compras", "fecha", "date"),
    ("compras", "num_albaran", "delivery_note_number"),
    ("compras", "notas", "notes"),
    ("compras", "coste_total", "total_cost"),
    # comandas
    ("comandas", "fecha", "date"),
    ("comandas", "num_comanda", "order_number"),
    ("comandas", "notas", "notes"),
    ("comandas", "enviada_at", "sent_at"),
    # comanda_items
    ("comanda_items", "cantidad", "quantity"),
    ("comanda_items", "precio_unitario_estimado", "estimated_unit_price"),
    ("comanda_items", "cantidad_rebuda", "received_quantity"),
    ("comanda_items", "notas", "notes"),
    # historial_compres
    ("historial_compres", "fecha", "date"),
    ("historial_compres", "artista", "artist"),
    ("historial_compres", "titulo", "title"),
    ("historial_compres", "sello", "label"),
    ("historial_compres", "formato", "format"),
    ("historial_compres", "cantidad", "quantity"),
    ("historial_compres", "precio_coste", "cost_price"),
    ("historial_compres", "notas", "notes"),
    # solicitudes_compra
    ("solicitudes_compra", "notas", "notes"),
    # solicitud_compra_items
    ("solicitud_compra_items", "artista", "artist"),
    ("solicitud_compra_items", "titulo", "title"),
    ("solicitud_compra_items", "sello", "label"),
    ("solicitud_compra_items", "formato", "format"),
    ("solicitud_compra_items", "cantidad", "quantity"),
    ("solicitud_compra_items", "notas", "notes"),
    # peticiones_cliente
    ("peticiones_cliente", "canal", "channel"),
    ("peticiones_cliente", "artista_lliure", "free_artist"),
    ("peticiones_cliente", "titulo_lliure", "free_title"),
    ("peticiones_cliente", "notas_cliente", "client_notes"),
    ("peticiones_cliente", "estado", "status"),
    ("peticiones_cliente", "precio_estimado", "estimated_price"),
    ("peticiones_cliente", "metodo_entrega_triat", "chosen_delivery_method"),
    ("peticiones_cliente", "notas_admin", "admin_notes"),
    # caja_sessions
    ("caja_sessions", "fecha_apertura", "opened_at"),
    ("caja_sessions", "fondo_inicial", "opening_float"),
    ("caja_sessions", "fecha_cierre", "closed_at"),
    ("caja_sessions", "total_ventas_efectivo", "total_cash_sales"),
    ("caja_sessions", "total_entradas", "total_cash_in"),
    ("caja_sessions", "total_salidas", "total_cash_out"),
    ("caja_sessions", "conteo_real", "actual_count"),
    ("caja_sessions", "notas", "notes"),
    # caja_movimientos
    ("caja_movimientos", "tipo", "type"),
    ("caja_movimientos", "concepto", "concept"),
    ("caja_movimientos", "importe", "amount"),
    ("caja_movimientos", "fecha", "date"),
    # devolucions_venta
    ("devolucions_venta", "cantidad", "quantity"),
    ("devolucions_venta", "motivo", "reason"),
    ("devolucions_venta", "destino_item", "item_destination"),
    ("devolucions_venta", "fecha", "date"),
    ("devolucions_venta", "notas", "notes"),
    # devolucions_compra
    ("devolucions_compra", "cantidad", "quantity"),
    ("devolucions_compra", "motivo", "reason"),
    ("devolucions_compra", "fecha", "date"),
    ("devolucions_compra", "notas", "notes"),
    # marges_config
    ("marges_config", "nom", "name"),
    ("marges_config", "percentatge", "percentage"),
    ("marges_config", "per_defecte_nou", "default_new"),
    ("marges_config", "per_defecte_segona_ma", "default_used"),
    ("marges_config", "actiu", "active"),
    # trams_enviament
    ("trams_enviament", "pais", "country"),
    ("trams_enviament", "pes_maxim_g", "max_weight_g"),
    ("trams_enviament", "preu", "price"),
    ("trams_enviament", "actiu", "active"),
    # tipus_iva (columnas que se quedaron fuera del piloto de la Fase 4 Etapa A)
    ("tipus_iva", "percentatge", "percentage"),
    ("tipus_iva", "es_rebu", "is_rebu"),
    ("tipus_iva", "per_defecte_nou", "default_new"),
    ("tipus_iva", "per_defecte_segona_ma", "default_used"),
    # configuracio_botiga
    ("configuracio_botiga", "nom_fiscal", "fiscal_name"),
    ("configuracio_botiga", "adreca", "address"),
    ("configuracio_botiga", "telefon", "phone"),
    ("configuracio_botiga", "email_contacte", "contact_email"),
    ("configuracio_botiga", "horari", "hours"),
    ("configuracio_botiga", "reserva_minuts", "reservation_minutes"),
    ("configuracio_botiga", "manteniment_actiu", "maintenance_active"),
    # despeses
    ("despeses", "num_factura", "invoice_number"),
    ("despeses", "data_factura", "invoice_date"),
    ("despeses", "data_venciment", "due_date"),
    ("despeses", "proveidor_nom", "supplier_name"),
    ("despeses", "categoria", "category"),
    ("despeses", "concepte", "concept"),
    ("despeses", "base_imposable", "taxable_base"),
    ("despeses", "iva_pct", "vat_pct"),
    ("despeses", "iva_import", "vat_amount"),
    ("despeses", "estat_pagament", "payment_status"),
    ("despeses", "data_pagament", "payment_date"),
    ("despeses", "metode_pagament", "payment_method"),
    # comptes_bancaris
    ("comptes_bancaris", "nom", "name"),
    ("comptes_bancaris", "entitat", "bank"),
    ("comptes_bancaris", "actiu", "active"),
    ("comptes_bancaris", "saldo_inicial", "opening_balance"),
    ("comptes_bancaris", "data_saldo_inicial", "opening_balance_date"),
    # moviments_bancaris
    ("moviments_bancaris", "data_operacio", "operation_date"),
    ("moviments_bancaris", "data_valor", "value_date"),
    ("moviments_bancaris", "concepte", "concept"),
    ("moviments_bancaris", "import_moviment", "movement_amount"),
    ("moviments_bancaris", "saldo", "balance"),
    ("moviments_bancaris", "estat", "status"),
    ("moviments_bancaris", "notes_conciliacio", "reconciliation_notes"),
    # periodes_comptables
    ("periodes_comptables", "mes", "month"),
    ("periodes_comptables", "tancat", "closed"),
    ("periodes_comptables", "data_tancament", "closed_at"),
    # caixa_diaria
    ("caixa_diaria", "data", "date"),
    ("caixa_diaria", "targeta_21", "card_21"),
    ("caixa_diaria", "targeta_4", "card_4"),
    ("caixa_diaria", "efectiu_21", "cash_21"),
    ("caixa_diaria", "efectiu_4", "cash_4"),
    ("caixa_diaria", "bono_cultural", "cultural_voucher"),
    # pagines
    ("pagines", "nom", "name"),
    ("pagines", "tipus", "type"),
    ("pagines", "posicio", "position"),
    ("pagines", "visible_menu", "menu_visible"),
    ("pagines", "contingut", "content"),
    # posts
    ("posts", "titulo", "title"),
    ("posts", "contenido", "content"),
    ("posts", "idioma", "language"),
    ("posts", "publicado_at", "published_at"),
    # events
    ("events", "titulo", "title"),
    ("events", "descripcion", "description"),
    ("events", "fecha", "date"),
    ("events", "lugar", "location"),
    # newsletter_campaigns
    ("newsletter_campaigns", "assumpte", "subject"),
    ("newsletter_campaigns", "contingut_html", "content_html"),
    ("newsletter_campaigns", "idioma", "language"),
    ("newsletter_campaigns", "estat", "status"),
    ("newsletter_campaigns", "enviament_iniciat_at", "sending_started_at"),
    ("newsletter_campaigns", "enviament_acabat_at", "sending_finished_at"),
    # newsletter_sends
    ("newsletter_sends", "estat", "status"),
    ("newsletter_sends", "enviat_at", "sent_at"),
    # stock_holds
    ("stock_holds", "cantidad", "quantity"),
]


def upgrade() -> None:
    for table, old, new in RENAMES:
        op.alter_column(table, old, new_column_name=new)


def downgrade() -> None:
    for table, old, new in reversed(RENAMES):
        op.alter_column(table, new, new_column_name=old)

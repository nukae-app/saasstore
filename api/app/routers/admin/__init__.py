"""Panel de administración: gestión del catálogo y de los pedidos.

El flujo de alta pensado para el día a día:
1. GET /admin/discogs/search?q=artista+titulo  -> resultados con metadatos
2. POST /admin/releases con los datos autocompletados (o a mano)
3. POST /admin/items con precio + grading -> la copia sale a la venta

Cada dominio vive en su propio módulo (uno por bloque de endpoints bajo el
mismo prefijo de URL); este paquete solo los agrega bajo un único `router`.
`require_discogs_enabled` se reexporta porque erp/comandas.py lo usa como
dependencia (el alta de comandas también gatea su import CSV al interruptor
de Discogs del tenant).
"""

from fastapi import APIRouter

from . import (
    catalog_bulk, discogs_sync, etiquetes, events, images, items, pagines, posts, releases, orders,
)
from ._shared import require_discogs_enabled

router = APIRouter()
for _modulo in (
    releases, items, catalog_bulk, orders, discogs_sync, etiquetes, images, posts, events, pagines,
):
    router.include_router(_modulo.router)

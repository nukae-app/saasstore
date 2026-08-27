"""ERP: entradas de stock (comandas a proveïdor + compres a particular) y
ventas externas (TPV + Discogs).

Flujo de entrada de stock a proveïdor:
  1. POST /admin/proveedores                    (si es proveedor nuevo)
  2. POST /admin/comandas                        (comanda amb línies; opcionalment
                                                  /admin/comandas/resolver-csv per
                                                  afegir-ne en bloc)
  3. POST /admin/comandas/{id}/enviar            (PDF al proveïdor)
  4. POST /admin/comandas/{id}/recepcio          (albarà: crea la Compra + Items reals,
                                                  poden fer-se vàries recepcions parcials)
  5. POST /admin/despeses/des-de-compres         (factura: agrupa una o més recepcions
                                                  encara sense facturar en una Despesa
                                                  pendent de pagament — comptabilitat.py)

Flujo de compra ràpida a particular (neix entregada):
  POST /admin/compras/particular

Flujo de venta externa:
  POST /admin/ventas-externas      (marca el item como retirado atómicamente
                                    y registra precio/canal para reporting)

Cada dominio vive en su propio módulo (uno por bloque de endpoints bajo el
mismo prefijo de URL); este paquete solo los agrega bajo un único `router`.
"""

from fastapi import APIRouter

from . import (
    caja, comandas, compras, devolucions, historial_compres, peticiones, proveedores,
    solicitudes_compra, ventas_externas,
)

router = APIRouter()
for _modulo in (
    proveedores, compras, comandas, historial_compres, solicitudes_compra, peticiones,
    ventas_externas, caja, devolucions,
):
    router.include_router(_modulo.router)

"""Router de comptabilitat: despeses, comptes bancaris, conciliació, informes i periodes.

Cada dominio vive en su propio módulo (uno por bloque de endpoints bajo el
mismo prefijo de URL); este paquete solo los agrega bajo un único `router`.
"""

from fastapi import APIRouter

from . import actius, aeat, banc, caixa_diaria, despeses, holded, llibres, periodes, proveedores, resultat

router = APIRouter()
for _modulo in (proveedores, despeses, banc, resultat, llibres, actius, holded, aeat, periodes, caixa_diaria):
    router.include_router(_modulo.router)

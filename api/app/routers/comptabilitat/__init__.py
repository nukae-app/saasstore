"""Router de comptabilitat: despeses, comptes bancaris, conciliació, informes i periodes.

Cada dominio vive en su propio módulo (uno por bloque de endpoints bajo el
mismo prefijo de URL); este paquete solo los agrega bajo un único `router`.
"""

from fastapi import APIRouter

from . import (
    actius, aeat, banc, caixa_diaria, comissions, despeses, despeses_imports, flux_caixa, holded, llibres, periodes,
    proveedores, remeses_pagament, resultat, tancament,
)

router = APIRouter()
for _modulo in (
    # despeses_imports ABANS que despeses: aquest últim té GET /despeses/{despesa_id}
    # (UUID), que si es registra primer intercepta /despeses/imports com si "imports"
    # fos un despesa_id (Starlette fa matching per ordre de registre, no especificitat).
    proveedores, despeses_imports, despeses, banc, resultat, llibres, actius, holded, aeat, periodes, caixa_diaria,
    flux_caixa, tancament, comissions, remeses_pagament,
):
    router.include_router(_modulo.router)

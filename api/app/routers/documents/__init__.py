"""Router de documents comercials (Bloc B1: pressupostos i albarans; Bloc
B2: factura de venda — veure docs/PLAN_PARIDAD_HOLDED.md). Cada dominio
vive en su propio módulo; este paquete solo los agrega bajo un único
`router`."""

from fastapi import APIRouter

from . import albarans, factures, pressupostos

router = APIRouter()
for _modulo in (pressupostos, albarans, factures):
    router.include_router(_modulo.router)

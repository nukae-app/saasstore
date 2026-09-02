"""Router de documents comercials no fiscals (Bloc B1, veure
docs/PLAN_PARIDAD_HOLDED.md): pressupostos i albarans. Cada dominio vive en
su propio módulo; este paquete solo los agrega bajo un único `router`."""

from fastapi import APIRouter

from . import albarans, pressupostos

router = APIRouter()
for _modulo in (pressupostos, albarans):
    router.include_router(_modulo.router)

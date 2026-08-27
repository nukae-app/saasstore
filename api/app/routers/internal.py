"""Endpoints de infraestructura interna — alcanzables solo contenedor a
contenedor (Caddy llamando directo a `api:8000`, nunca a través del
listener público), no por navegador/cliente externo. Sin autenticación a
propósito: no exponen ni aceptan nada sensible, solo un sí/no. Fase 4 del
roadmap de superadmin (ver docs/ARQUITECTURA_CORE_VERTICAL.md y el plan
en /Users/paumartinez/.claude/plans/rustling-foraging-wind.md)."""

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db_unscoped
from ..tenancy import resolve_tenant_by_domain

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/caddy/ask-domain")
def ask_domain(domain: str, db=Depends(get_db_unscoped)):
    """Lo llama la directiva `on_demand_tls.ask` de Caddy (ver
    infra/Caddyfile) antes de pedir un certificado nuevo a Let's Encrypt
    para un host sin bloque estático — sin este filtro, cualquier hostname
    que resuelva a este servidor podría disparar peticiones de certificado
    y agotar el rate limit de ACME de la cuenta. Reutiliza exactamente la
    misma resolución que ya usa cualquier request tenant-scoped
    (`resolve_tenant_by_domain`, filtra por `Tenant.activo=True`), así que
    un tenant suspendido (Fase 2) tampoco consigue certificado nuevo.
    Caddy solo mira el código de estado: 200 = adelante, cualquier otra
    cosa = deniega."""
    if resolve_tenant_by_domain(db, domain) is None:
        raise HTTPException(404)
    return {"ok": True}

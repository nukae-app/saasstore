"""Cobrament diari de les subscripcions del club del disc vençudes avui.
Cada subscripció té la seva pròpia data d'aniversari (`proxima_facturacio`),
no cal que coincideixi amb el dia 1 de mes per a tothom. La feina real
(seleccionar/cobrar) viu a services/subscripcions.py; aquesta tasca només
n'orquestra l'execució periòdica i registra el resultat.

Fase 4: `Subscripcio`/`CobramentSubscripcio` són ara TenantScoped — aquesta
tasca obre la seva pròpia sessió amb `SessionLocal()` (no passa per
`get_db`, no hi ha request), així que cal iterar tots els tenants i fixar
`scoped_to` a cada volta (mateix patró que tasks/peticiones.py). Sense
això, amb RLS activat a `subscripcions`, la consulta no veuria res de cap
tenant i la facturació deixaria de cobrar a tothom en silenci."""

import logging

from sqlalchemy import select

from ..celery_app import celery_app
from ..database import SessionLocal
from ..models import EstatCobrament, Tenant
from ..services.subscripcions import facturar_subscripcions_vencudes
from ..tenancy import scoped_to

log = logging.getLogger(__name__)


@celery_app.task(name="subscripcions.facturar_pendents")
def facturar_pendents() -> dict:
    db = SessionLocal()
    total_cobraments = total_cobrats = total_fallits = 0
    try:
        tenants = list(db.scalars(select(Tenant).where(Tenant.activo.is_(True))))
        for tenant in tenants:
            with scoped_to(db, tenant.id):
                cobraments = facturar_subscripcions_vencudes(db)
            cobrats = sum(1 for c in cobraments if c.estat == EstatCobrament.cobrat)
            fallits = len(cobraments) - cobrats
            total_cobraments += len(cobraments)
            total_cobrats += cobrats
            total_fallits += fallits
        if total_cobraments:
            log.info(
                "subscripcions: %d cobraments (%d ok, %d fallits)",
                total_cobraments, total_cobrats, total_fallits,
            )
        return {"cobraments": total_cobraments, "cobrats": total_cobrats, "fallits": total_fallits}
    finally:
        db.close()

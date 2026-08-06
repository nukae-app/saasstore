"""Cobrament diari de les subscripcions del club del disc vençudes avui.
Cada subscripció té la seva pròpia data d'aniversari (`proxima_facturacio`),
no cal que coincideixi amb el dia 1 de mes per a tothom. La feina real
(seleccionar/cobrar) viu a services/subscripcions.py; aquesta tasca només
n'orquestra l'execució periòdica i registra el resultat."""

import logging

from ..celery_app import celery_app
from ..database import SessionLocal
from ..models import EstatCobrament
from ..services.subscripcions import facturar_subscripcions_vencudes

log = logging.getLogger(__name__)


@celery_app.task(name="subscripcions.facturar_pendents")
def facturar_pendents() -> dict:
    db = SessionLocal()
    try:
        cobraments = facturar_subscripcions_vencudes(db)
        cobrats = sum(1 for c in cobraments if c.estat == EstatCobrament.cobrat)
        fallits = len(cobraments) - cobrats
        if cobraments:
            log.info("subscripcions: %d cobraments (%d ok, %d fallits)", len(cobraments), cobrats, fallits)
        return {"cobraments": len(cobraments), "cobrats": cobrats, "fallits": fallits}
    finally:
        db.close()

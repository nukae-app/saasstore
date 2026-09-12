"""Instància de Celery per a tasques en segon pla (enviament massiu de
newsletters, alliberament de reserves caducades de peticions de client).

La sincronització de catàleg amb Discogs ja NO es fa aquí: es feia via un
CSV de Google Sheet (app/tasks/catalog_sync.py, ara sense schedule) i s'ha
substituït per `scripts/sync_discogs_inventory.py`, que llegeix directament
l'inventari real de Discogs. Es crida per cron de l'host (fora de Celery)
perquè el DISCOGS_TOKEN de producció només l'ha de veure aquest script, no
els contenidors api/worker/beat mentre encara estem de proves — veure
scripts/run_discogs_sync.sh.
"""

from celery import Celery
from celery.schedules import crontab

from .config import get_settings

_settings = get_settings()

celery_app = Celery(
    "ultralocal",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=[
        "app.tasks.health", "app.tasks.newsletter", "app.tasks.peticiones", "app.tasks.pricing",
        "app.tasks.subscripcions",
    ],
)

celery_app.conf.beat_schedule = {
    "worker-heartbeat": {
        "task": "health.heartbeat",
        "schedule": crontab(minute="*/1"),
    },
    "release-expired-peticiones": {
        "task": "peticiones.release_expired_reservations",
        "schedule": crontab(minute="*/30"),
    },
    "recompute-pricing": {
        "task": "pricing.recompute_all_tenants",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # Reactivada (2026-09-12, ver docs/PLAN_COBRAMENTS_PAGAMENTS.md): el
    # comentario que la excluía ("desactivada en la fase 1 del núcleo
    # multi-tenant") estaba obsoleto — app/tasks/subscripcions.py ya itera
    # tenants con scoped_to (mismo patrón que tasks/peticiones.py) desde
    # hace tiempo, solo nunca se volvió a dar de alta aquí. Sin esto, ningún
    # tenant con Club del disc activo estaba cobrando renovaciones de verdad.
    "facturar-subscripcions-pendents": {
        "task": "subscripcions.facturar_pendents",
        "schedule": crontab(minute=0, hour=6),
    },
}

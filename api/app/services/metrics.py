"""Mètriques de negoci que cap codi d'estat HTTP genèric captura: Redsys
sempre respon 200 a la notificació (autoritzat o denegat), i els
enviaments de newsletter passen dins d'una tasca de Celery sense petició
HTTP associada. `prometheus-fastapi-instrumentator` ja exposa aquest
`REGISTRY` per defecte a /metrics, així que amb declarar-les n'hi ha prou."""

from datetime import datetime, timezone

from prometheus_client import Counter, Gauge

from ..redis_client import get_redis_client

redsys_payment_result_total = Counter(
    "redsys_payment_result_total", "Resultat de notificacions de pagament Redsys", ["result"]
)
newsletter_send_result_total = Counter(
    "newsletter_send_result_total", "Resultat d'enviaments de newsletter", ["result"]
)
celery_queue_depth = Gauge("celery_queue_depth", "Tasques pendents a la cua per defecte de Celery")
celery_queue_depth.set_function(lambda: get_redis_client().llen("celery"))


def _seconds_since_last_heartbeat() -> float:
    """-1 si mai hi ha hagut heartbeat (worker/beat mai arrencats): mai és
    un valor real vàlid, així que fa evident aquest cas en un panell/alerta
    en comptes de confondre's amb "fa 0 segons"."""
    from ..tasks.health import HEARTBEAT_KEY

    raw = get_redis_client().get(HEARTBEAT_KEY)
    if raw is None:
        return -1
    last = datetime.fromisoformat(raw.decode())
    return (datetime.now(timezone.utc) - last).total_seconds()


celery_worker_heartbeat_seconds_ago = Gauge(
    "celery_worker_heartbeat_seconds_ago", "Segons des de l'últim heartbeat del worker/beat de Celery"
)
celery_worker_heartbeat_seconds_ago.set_function(_seconds_since_last_heartbeat)

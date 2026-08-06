"""Heartbeat del worker/beat: escriu un timestamp a Redis cada minut
perquè /health pugui confirmar que les tasques en segon pla es processen
de veritat, no només que Redis (el broker) respon."""

from datetime import datetime, timezone

from ..celery_app import celery_app
from ..redis_client import get_redis_client

HEARTBEAT_KEY = "celery:heartbeat"
# TTL una mica més gran que l'interval del beat_schedule (1 min): si el
# worker/beat es pengen, la clau caduca sola en comptes de quedar-se amb
# un timestamp vell dient fals "ok".
HEARTBEAT_TTL_SECONDS = 180


@celery_app.task(name="health.heartbeat")
def heartbeat() -> None:
    get_redis_client().set(HEARTBEAT_KEY, datetime.now(timezone.utc).isoformat(), ex=HEARTBEAT_TTL_SECONDS)

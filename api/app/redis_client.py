"""Client Redis compartit: usat per /health (ping, heartbeat del worker,
profunditat de cua) i per api/app/tasks/health.py. Connexions curtes amb
timeout baix — mai ha de convertir cap petició en lenta si Redis penja."""

import redis

from .config import get_settings


def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2)

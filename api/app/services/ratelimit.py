"""Limitador de llamadas a Discogs compartido entre procesos.

La API de Discogs permite ~60 llamadas/min por token (ventana móvil de 60 s).
El espaciado local de `services/discogs.py::_throttle` es por proceso: con la
API (2 workers), Celery (2 procesos) y acciones manuales a la vez, el total
sobrepasa el límite. Aquí el espaciado se hace en Redis, por token (se guarda
solo un hash, nunca el token), y se adapta a lo que dice Discogs:

- Un hueco mínimo de 1,1 s entre llamadas (~54/min) para todo el que use el token.
- Si una respuesta trae `X-Discogs-Ratelimit-Remaining` casi a cero, o un 429,
  todos hacen una pausa (15 s / 60 s).
- Si Redis no está disponible, se devuelve False y el llamador sigue con su
  espaciado local (y no se vuelve a probar Redis durante 30 s).

Se engancha en un único punto: el cliente HTTP (`discogs._client`)."""

import hashlib
import logging
import time
from functools import lru_cache

import redis

from ..config import get_settings

log = logging.getLogger(__name__)

SPACING_MS = 1100
PAUSE_ON_429_MS = 60_000
PAUSE_LOW_REMAINING_MS = 15_000
LOW_REMAINING = 3
MAX_WAIT_S = 120.0
REDIS_DOWN_FOR_S = 30.0

_down_until = 0.0


def _now() -> float:
    return time.monotonic()


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


@lru_cache
def _pool() -> redis.ConnectionPool:
    return redis.ConnectionPool.from_url(
        get_settings().redis_url, socket_connect_timeout=1, socket_timeout=2, max_connections=10
    )


def _redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool())


def token_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _keys(token: str) -> tuple[str, str]:
    k = token_key(token)
    return f"discogs:rl:slot:{k}", f"discogs:rl:pause:{k}"


def acquire(token: str) -> bool:
    """Espera su turno compartido. True si lo ha gestionado Redis; False si no
    hay Redis (el llamador usa entonces su espaciado local)."""
    global _down_until
    if _now() < _down_until:
        return False
    slot, pause = _keys(token)
    try:
        r = _redis()
        deadline = _now() + MAX_WAIT_S
        while True:
            pausa_ms = r.pttl(pause)
            if pausa_ms and pausa_ms > 0:
                _sleep(min(pausa_ms, 5000) / 1000)
            elif r.set(slot, "1", nx=True, px=SPACING_MS):
                return True
            else:
                _sleep(max(r.pttl(slot), 20) / 1000)
            if _now() > deadline:
                log.warning("ratelimit: espera máxima superada, se sigue igualmente")
                return True
    except redis.RedisError:
        _down_until = _now() + REDIS_DOWN_FOR_S
        log.warning("ratelimit: Redis no disponible, espaciado local durante %ss", REDIS_DOWN_FOR_S)
        return False


def note_response(token: str, status_code: int, headers) -> None:
    """Ajusta la pausa común según la respuesta de Discogs (429 o poco margen)."""
    pausa_ms = 0
    if status_code == 429:
        pausa_ms = PAUSE_ON_429_MS
    else:
        try:
            if int(headers.get("X-Discogs-Ratelimit-Remaining", "")) <= LOW_REMAINING:
                pausa_ms = PAUSE_LOW_REMAINING_MS
        except (TypeError, ValueError):
            return
    if not pausa_ms:
        return
    try:
        _redis().set(_keys(token)[1], "1", px=pausa_ms)
    except redis.RedisError:
        pass

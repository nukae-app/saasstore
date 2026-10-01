"""Estat dels treballs de sincronització d'inventari de Discogs (pantalla
/admin/canals/discogs). El treball corre en un worker de Celery
(`tasks/discogs.py`) i el seu estat/progrés/informe viuen a Redis, perquè
l'API els pugui consultar mentre dura i sobrevisqui a un reinici de l'API.

Per tenant: un únic treball "actual" (no se'n poden llançar dos alhora) i la
marca de l'última simulació acabada — l'execució real només es permet si hi
ha una simulació recent, per forçar a revisar abans d'aplicar."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import redis

from ..config import get_settings

JOB_TTL_SECONDS = 7 * 24 * 3600
STALE_AFTER = timedelta(minutes=10)  # sense senyal de vida: el worker s'ha mort
DRY_RUN_VALID_FOR = timedelta(hours=24)
MAX_LOG_LINES = 60


class JobConflict(Exception):
    """Ja hi ha un treball en marxa per a aquest tenant."""


class JobPrecondition(Exception):
    """No es compleix un requisit (p. ex. cal una simulació recent)."""


class RedisKV:
    def __init__(self) -> None:
        self._r = redis.Redis(connection_pool=_pool())

    def get(self, key: str) -> str | None:
        value = self._r.get(key)
        return value.decode() if isinstance(value, bytes) else value

    def set(self, key: str, value: str, ex: int) -> None:
        self._r.set(key, value, ex=ex)


class MemoryKV:
    """Per als tests: sense Redis."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str, ex: int) -> None:
        self.data[key] = value


@lru_cache
def _pool() -> redis.ConnectionPool:
    return redis.ConnectionPool.from_url(
        get_settings().redis_url, socket_connect_timeout=3, socket_timeout=5, max_connections=10
    )


def _kv():
    return RedisKV()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _key_job(tenant_id) -> str:
    return f"discogs_inv:job:{tenant_id}"


def _key_rows(tenant_id, job_id: str) -> str:
    return f"discogs_inv:rows:{tenant_id}:{job_id}"


def _key_dry(tenant_id) -> str:
    return f"discogs_inv:lastdry:{tenant_id}"


def _load(key: str) -> dict | list | None:
    raw = _kv().get(key)
    return json.loads(raw) if raw else None


def _save(key: str, value) -> None:
    _kv().set(key, json.dumps(value, ensure_ascii=False, default=str), ex=JOB_TTL_SECONDS)


def get_job(tenant_id) -> dict | None:
    """Treball actual del tenant. Si està 'en marxa' però fa massa que no dona
    senyal de vida, es reporta com a `encallat` (el worker s'ha mort)."""
    job = _load(_key_job(tenant_id))
    if job and job["status"] in ("queued", "running"):
        if _now() - datetime.fromisoformat(job["updated_at"]) > STALE_AFTER:
            job = {**job, "status": "stalled"}
    return job


def start_job(tenant_id, mode: str, options: dict) -> dict:
    """Crea el treball (estat `queued`). Llança JobConflict si n'hi ha un en
    marxa, i JobPrecondition si és una execució real sense simulació recent."""
    actual = get_job(tenant_id)
    if actual and actual["status"] in ("queued", "running"):
        raise JobConflict("Ja hi ha una sincronització en marxa.")

    if mode == "apply":
        dry = _load(_key_dry(tenant_id))
        if not dry or _now() - datetime.fromisoformat(dry["finished_at"]) > DRY_RUN_VALID_FOR:
            raise JobPrecondition("Cal fer abans una simulació (de menys de 24 h) i revisar-la.")

    now = _iso(_now())
    job = {
        "id": uuid.uuid4().hex, "mode": mode, "status": "queued", "phase": None, "done": 0, "total": 0,
        "created_at": now, "started_at": None, "finished_at": None, "updated_at": now,
        "options": options, "summary": None, "error": None, "log": [], "rows_count": 0,
    }
    _save(_key_job(tenant_id), job)
    return job


def update_job(tenant_id, job_id: str, **fields) -> dict | None:
    """Actualitza el treball actual (si encara és aquest) i renova `updated_at`."""
    job = _load(_key_job(tenant_id))
    if not job or job["id"] != job_id:
        return None
    job.update(fields)
    job["updated_at"] = _iso(_now())
    _save(_key_job(tenant_id), job)
    return job


def append_log(tenant_id, job_id: str, line: str) -> None:
    job = _load(_key_job(tenant_id))
    if not job or job["id"] != job_id:
        return
    job["log"] = (job["log"] + [line])[-MAX_LOG_LINES:]
    job["updated_at"] = _iso(_now())
    _save(_key_job(tenant_id), job)


def save_rows(tenant_id, job_id: str, rows: list[dict]) -> None:
    _save(_key_rows(tenant_id, job_id), rows)


def load_rows(tenant_id, job_id: str) -> list[dict] | None:
    return _load(_key_rows(tenant_id, job_id))


def record_dry_run(tenant_id, job_id: str, summary: dict) -> None:
    _save(_key_dry(tenant_id), {"job_id": job_id, "finished_at": _iso(_now()), "summary": summary})


def last_dry_run(tenant_id) -> dict | None:
    return _load(_key_dry(tenant_id))

"""Endpoint de salut: comprova Postgres, Redis, i que el worker de Celery
segueix processant tasques de veritat (no només que Redis respon). Usat
per Grafana Cloud Synthetic Monitoring i per comprovacions manuals
(`curl https://.../api/health`)."""

import json
import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..rate_limit import limiter
from ..redis_client import get_redis_client
from ..tasks.health import HEARTBEAT_KEY

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

# Nom de cua per defecte de Celery (no hi ha `-Q` custom enlloc del projecte).
_CELERY_QUEUE_NAME = "celery"


def _check_database(db: Session) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_redis() -> dict:
    try:
        get_redis_client().ping()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_worker() -> dict:
    """El worker/beat escriuen un heartbeat cada minut (veure
    tasks/health.py) amb TTL de 3 min: si la clau no hi és, o el worker
    s'ha penjat, o mai ha arribat a arrencar — en cap cas Redis sol pot
    confirmar que les tasques en segon pla es processen de veritat."""
    try:
        last = get_redis_client().get(HEARTBEAT_KEY)
        if last is None:
            return {"ok": False, "error": "cap heartbeat recent del worker"}
        return {"ok": True, "last_heartbeat": last.decode()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _queue_depth() -> int | None:
    try:
        return get_redis_client().llen(_CELERY_QUEUE_NAME)
    except Exception:
        return None


@router.get("/health")
def health(response: Response, db: Session = Depends(get_db)):
    checks = {"database": _check_database(db), "redis": _check_redis(), "worker": _check_worker()}
    overall_ok = all(c["ok"] for c in checks.values())
    response.status_code = 200 if overall_ok else 503
    return {
        "status": "ok" if overall_ok else "error",
        "checks": checks,
        # Informatiu: una cua llarga no fa fallar el health check per si
        # sola (podria ser només una punta puntual de trànsit), però val
        # la pena veure-ho sense haver d'anar a Grafana.
        "queue_depth": _queue_depth(),
    }


@router.post("/csp-report", status_code=204, include_in_schema=False)
@limiter.limit("60/minute")
async def csp_report(request: Request):
    """Receptor dels informes de `Content-Security-Policy-Report-Only` (ver
    infra/Caddyfile). Només els registra al log (que Alloy envia a Grafana) per
    poder revisar què bloquejaria la CSP abans d'activar-la. Cos limitat a 8 KB
    i serialitzat amb json.dumps per evitar injecció de línies de log."""
    raw = (await request.body())[:8192]
    try:
        report = json.loads(raw)
    except ValueError:
        return
    logger.warning("csp-violation %s", json.dumps(report, ensure_ascii=False)[:2000])

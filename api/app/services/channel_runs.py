"""Historial persistente de sincronizaciones de canal (`channel_sync_runs`).

El estado en vivo de un trabajo (progreso, log) vive en Redis y caduca
(services/discogs_jobs.py); aquí queda el registro duradero: cuándo se lanzó,
con qué opciones, cómo acabó y el informe por item. Mismo id que el trabajo
de Redis. Las funciones hacen commit (se usan fuera de la transacción de
negocio, desde el endpoint o la tarea)."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CHANNEL_DISCOGS, ChannelSyncRun
from ..models.channels import RUN_QUEUED, RUN_RUNNING

STALE_AFTER = timedelta(minutes=10)
_KIND_BY_MODE = {"reconcile": "reconcile_apply", "audit": "audit", "pricing_preview": "pricing_preview"}


def _json_safe(value):
    """Decimal/UUID/datetime -> cadenas, para poder guardar el informe en una columna JSON."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def create_run(db: Session, job: dict, channel: str = CHANNEL_DISCOGS) -> None:
    db.add(ChannelSyncRun(
        id=job["id"], channel=channel,
        kind=_KIND_BY_MODE.get(job["mode"], f"inventory_{job['mode']}"), status=RUN_QUEUED,
        options=job.get("options"),
    ))
    db.commit()


def update_run(db: Session, run_id: str, **fields) -> None:
    run = db.get(ChannelSyncRun, run_id)
    if run is None:
        return
    if "report" in fields and fields["report"] is not None:
        fields["report"] = _json_safe(fields["report"])
    if "summary" in fields and fields["summary"] is not None:
        fields["summary"] = _json_safe(fields["summary"])
    for key, value in fields.items():
        setattr(run, key, value)
    db.commit()


def list_runs(db: Session, limit: int = 20, channel: str = CHANNEL_DISCOGS) -> list[ChannelSyncRun]:
    return list(db.scalars(
        select(ChannelSyncRun).where(ChannelSyncRun.channel == channel)
        .order_by(ChannelSyncRun.created_at.desc()).limit(limit)
    ).all())


def load_report(db: Session, run_id: str) -> list[dict] | None:
    run = db.get(ChannelSyncRun, run_id)
    return run.report if run is not None else None


def effective_status(run: ChannelSyncRun, current_job: dict | None) -> str:
    """Estado a mostrar: un trabajo 'en marcha' que no es el actual de Redis y lleva
    rato sin cerrarse se da por encallado (el worker murió antes de terminarlo)."""
    if run.status not in (RUN_QUEUED, RUN_RUNNING):
        return run.status
    if current_job and current_job["id"] == run.id:
        return current_job["status"]
    created = run.created_at if run.created_at.tzinfo else run.created_at.replace(tzinfo=timezone.utc)
    return "stalled" if datetime.now(timezone.utc) - created > STALE_AFTER else run.status

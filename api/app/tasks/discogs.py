"""Sincronització de l'inventari de Discogs en segon pla (pantalla
/admin/canals/discogs). Veure services/discogs_inventory_sync.py (lògica) i
services/discogs_jobs.py (estat a Redis)."""

import logging
import uuid
from datetime import datetime, timezone

from ..celery_app import celery_app
from ..database import SessionLocal
from ..models import Tenant
from ..services import discogs_jobs as jobs
from ..services.discogs_inventory_sync import InventorySyncAbort, run_inventory_sync
from ..tenancy import scoped_to

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@celery_app.task(name="discogs.inventory_sync")
def inventory_sync(tenant_id: str, job_id: str) -> None:
    job = jobs.get_job(tenant_id)
    if not job or job["id"] != job_id:
        return
    opts = job["options"]
    dry_run = job["mode"] == "dry_run"
    jobs.update_job(tenant_id, job_id, status="running", started_at=_now_iso())

    db = SessionLocal()
    try:
        tenant = db.get(Tenant, uuid.UUID(tenant_id))
        if tenant is None:
            jobs.update_job(tenant_id, job_id, status="error", error="Tenant no trobat", finished_at=_now_iso())
            return
        with scoped_to(db, tenant.id):
            result = run_inventory_sync(
                db, tenant, dry_run=dry_run, limit=opts.get("limit", 0), force=opts.get("force", False),
                reobrir_adopcio=opts.get("reobrir_adopcio", False),
                log=lambda line: jobs.append_log(tenant_id, job_id, line),
                progress=lambda fase, feta, total: jobs.update_job(
                    tenant_id, job_id, phase=fase, done=feta, total=total
                ),
            )
        jobs.save_rows(tenant_id, job_id, result.rows)
        jobs.update_job(
            tenant_id, job_id, status="done", summary=result.summary, rows_count=len(result.rows),
            finished_at=_now_iso(),
        )
        if dry_run:
            jobs.record_dry_run(tenant_id, job_id, result.summary)
    except InventorySyncAbort as exc:
        db.rollback()
        jobs.update_job(tenant_id, job_id, status="error", error=str(exc), error_kind="abort", finished_at=_now_iso())
    except Exception as exc:  # noqa: BLE001 — qualsevol fallada s'ha de veure a la pantalla
        db.rollback()
        log.exception("discogs.inventory_sync ha fallat (tenant=%s)", tenant_id)
        jobs.update_job(
            tenant_id, job_id, status="error", error=f"Error inesperat: {exc}", error_kind="error",
            finished_at=_now_iso(),
        )
    finally:
        db.close()

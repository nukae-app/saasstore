"""Trabajos en segundo plano del canal Discogs: sincronización de inventario de la carga
inicial (pantalla de Sincronització), aplicación del plan de reconciliación (pestaña Listings)
y su ejecución programada. Lógica en services/discogs_inventory_sync.py y
services/channel_apply.py; estado en vivo en Redis (services/discogs_jobs.py) e historial
persistente en channel_sync_runs (services/channel_runs.py)."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from ..celery_app import celery_app
from ..database import SessionLocal
from ..models import ConfiguracioBotiga, Tenant
from ..services import channel_reconciler as rec
from ..services import channel_runs, discogs_jobs as jobs
from ..services.channel_alerts import raise_alert
from ..services.channel_apply import ReconcileAbort, run_reconcile, scheduled_actions
from ..services.channel_audit import AuditAbort, run_audit
from ..services.channel_notifications import send_pending
from ..services.discogs_backup import BackupAbort, run_discogs_backup
from ..services.channel_pricing import PricingAbort, run_pricing_preview
from ..services.channel_orders import OrdersPullError, is_due, pull_orders
from ..services.channel_settings import get_settings
from ..services.discogs_inventory_sync import InventorySyncAbort, run_inventory_sync
from ..services.discogs_sync import adopcio_feta, get_discogs_token_if_enabled
from ..services.discogs import is_read_only
from ..tenancy import scoped_to

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _persist(db, tenant_uuid: uuid.UUID, run_id: str, **fields) -> None:
    """Actualiza el historial persistente. Con su propio `scoped_to`: los manejadores de
    error corren fuera del bloque principal y, sin tenant fijado, RLS devolvería 0 filas."""
    try:
        with scoped_to(db, tenant_uuid):
            channel_runs.update_run(db, run_id, **fields)
    except Exception:  # noqa: BLE001 — el historial nunca debe tumbar el trabajo
        db.rollback()
        log.warning("discogs: no se pudo actualizar el historial (%s)", run_id, exc_info=True)


def _run_inventory(db, tenant, job, log_fn, progress):
    opts = job["options"]
    return run_inventory_sync(
        db, tenant, dry_run=job["mode"] == "dry_run", limit=opts.get("limit", 0), force=opts.get("force", False),
        reobrir_adopcio=opts.get("reobrir_adopcio", False), log=log_fn, progress=progress, actor=opts.get("actor"),
    )


def _run_reconcile(db, tenant, job, log_fn, progress):
    opts = job["options"]
    item_ids = {uuid.UUID(x) for x in opts["item_ids"]} if opts.get("item_ids") else None
    return run_reconcile(
        db, tenant, actions=set(opts["actions"]) if opts.get("actions") else None, item_ids=item_ids,
        actor=opts.get("actor"), force=opts.get("force", False), skip_errors=opts.get("scheduled", False),
        log_fn=log_fn, progress=progress,
    )


def _run_pricing(db, tenant, job, log_fn, progress):
    opts = job["options"]
    return run_pricing_preview(
        db, tenant, item_ids={uuid.UUID(x) for x in opts["item_ids"]} if opts.get("item_ids") else None,
        limit=opts.get("limit", 200), factor=opts.get("factor", 1.0), step=opts.get("step", 0.5),
        min_diff_pct=opts.get("min_diff_pct", 5.0), log_fn=log_fn, progress=progress,
    )


def _run_backup(db, tenant, job, log_fn, progress):
    opts = job["options"]
    return run_discogs_backup(
        db, tenant, orders=opts.get("orders", True), actor=opts.get("actor"), log_fn=log_fn, progress=progress,
    )


def _run_audit(db, tenant, job, log_fn, progress):
    return run_audit(db, tenant, log_fn=log_fn, progress=progress)


def _alert_failed(db, tenant_uuid: uuid.UUID, job: dict, message: str) -> None:
    """Un fallo de trabajo de fondo (programado o inesperado) no puede pasar desapercibido."""
    try:
        with scoped_to(db, tenant_uuid):
            raise_alert(db, "sync_failed", f"job:{job['id']}", f"Treball '{job['mode']}' fallit: {message}", severity="error",
                        detail={"job": job["id"], "mode": job["mode"]})
            db.commit()
            send_pending(db)
    except Exception:  # noqa: BLE001
        db.rollback()
        log.warning("discogs: no se pudo registrar la alerta de fallo (%s)", job["id"], exc_info=True)


def _execute(tenant_id: str, job_id: str, runner) -> None:
    job = jobs.get_job(tenant_id)
    if not job or job["id"] != job_id:
        return
    jobs.update_job(tenant_id, job_id, status="running", started_at=_now_iso())

    tenant_uuid = uuid.UUID(tenant_id)
    db = SessionLocal()
    try:
        tenant = db.get(Tenant, tenant_uuid)
        if tenant is None:
            jobs.update_job(tenant_id, job_id, status="error", error="Tenant no trobat", finished_at=_now_iso())
            return
        _persist(db, tenant_uuid, job_id, status="running", started_at=datetime.now(timezone.utc))
        with scoped_to(db, tenant.id):
            result = runner(
                db, tenant, job,
                lambda line: jobs.append_log(tenant_id, job_id, line),
                lambda fase, feta, total: jobs.update_job(tenant_id, job_id, phase=fase, done=feta, total=total),
            )
        jobs.save_rows(tenant_id, job_id, result.rows)
        jobs.update_job(
            tenant_id, job_id, status="done", summary=result.summary, rows_count=len(result.rows),
            finished_at=_now_iso(),
        )
        _persist(
            db, tenant_uuid, job_id, status="done", summary=result.summary, rows_count=len(result.rows),
            report=result.rows, finished_at=datetime.now(timezone.utc),
        )
        if job["mode"] == "dry_run":
            jobs.record_dry_run(tenant_id, job_id, result.summary)
        with scoped_to(db, tenant_uuid):
            send_pending(db)  # avisos de las alertas que haya generado el propio trabajo
    except (InventorySyncAbort, ReconcileAbort, AuditAbort, PricingAbort, BackupAbort) as exc:
        db.rollback()
        jobs.update_job(tenant_id, job_id, status="error", error=str(exc), error_kind="abort", finished_at=_now_iso())
        _persist(db, tenant_uuid, job_id, status="error", error=str(exc), error_kind="abort",
                 finished_at=datetime.now(timezone.utc))
        if job["options"].get("scheduled"):  # si lo lanzó una persona, ya lo ve en pantalla
            _alert_failed(db, tenant_uuid, job, str(exc))
    except Exception as exc:  # noqa: BLE001 — qualsevol fallada s'ha de veure a la pantalla
        db.rollback()
        log.exception("discogs: el treball %s ha fallat (tenant=%s)", job["mode"], tenant_id)
        jobs.update_job(
            tenant_id, job_id, status="error", error=f"Error inesperat: {exc}", error_kind="error",
            finished_at=_now_iso(),
        )
        _persist(db, tenant_uuid, job_id, status="error", error=f"Error inesperat: {exc}", error_kind="error",
                 finished_at=datetime.now(timezone.utc))
        _alert_failed(db, tenant_uuid, job, f"error inesperat: {exc}")
    finally:
        db.close()


@celery_app.task(name="discogs.inventory_sync")
def inventory_sync(tenant_id: str, job_id: str) -> None:
    _execute(tenant_id, job_id, _run_inventory)


@celery_app.task(name="discogs.backup")
def backup(tenant_id: str, job_id: str) -> None:
    _execute(tenant_id, job_id, _run_backup)


@celery_app.task(name="discogs.pricing_preview")
def pricing_preview(tenant_id: str, job_id: str) -> None:
    _execute(tenant_id, job_id, _run_pricing)


@celery_app.task(name="discogs.audit")
def audit(tenant_id: str, job_id: str) -> None:
    _execute(tenant_id, job_id, _run_audit)


@celery_app.task(name="discogs.audit_scheduled")
def audit_scheduled() -> dict:
    """Una vez al día: audita cada tenant con Discogs activo y la carga inicial hecha."""
    db = SessionLocal()
    lanzados = 0
    try:
        for tenant in db.scalars(select(Tenant).where(Tenant.activo.is_(True))).all():
            with scoped_to(db, tenant.id):
                config = db.scalar(select(ConfiguracioBotiga))
                if not config or not config.discogs_habilitat or adopcio_feta(db) is None:
                    continue
                if get_discogs_token_if_enabled(db, tenant.id) is None:
                    continue
                try:
                    job = jobs.start_job(str(tenant.id), "audit", {"scheduled": True, "actor": "sistema"})
                except (jobs.JobConflict, jobs.JobPrecondition):
                    continue
                channel_runs.create_run(db, job)
                audit.delay(str(tenant.id), job["id"])
                lanzados += 1
    finally:
        db.close()
    return {"lanzados": lanzados}


@celery_app.task(name="discogs.reconcile_apply")
def reconcile_apply(tenant_id: str, job_id: str) -> None:
    _execute(tenant_id, job_id, _run_reconcile)


@celery_app.task(name="discogs.reconcile_scheduled")
def reconcile_scheduled() -> dict:
    """Cada 15 min: por cada tenant con Discogs activo y en lectura/escritura, aplica sola la parte
    segura del plan (retirar lo que ya no está a la venta; publicar y actualizar precios solo si la
    publicación automática está activada). Solo después de la carga inicial. Si ya hay un trabajo en
    marcha o no hay nada que hacer, no hace nada."""
    db = SessionLocal()
    lanzados = 0
    try:
        for tenant in db.scalars(select(Tenant).where(Tenant.activo.is_(True))).all():
            with scoped_to(db, tenant.id):
                config = db.scalar(select(ConfiguracioBotiga))
                if not config or not config.discogs_habilitat or config.discogs_solo_lectura:
                    continue
                if adopcio_feta(db) is None:
                    continue
                settings = get_settings(db)
                db.commit()
                token = get_discogs_token_if_enabled(db, tenant.id)
                if not settings.sync_auto or token is None or is_read_only(token):
                    continue
                wanted = scheduled_actions(settings)
                pendientes = [
                    r for r in rec.plan_rows(db, settings.recargo_pct)
                    if r["accio"] in wanted and r["listing_status"] != "error"
                ]
                if not pendientes:
                    continue
                try:
                    job = jobs.start_job(
                        str(tenant.id), "reconcile",
                        {"actions": sorted(wanted), "scheduled": True, "actor": "sistema"},
                    )
                except (jobs.JobConflict, jobs.JobPrecondition):
                    continue
                channel_runs.create_run(db, job)
                reconcile_apply.delay(str(tenant.id), job["id"])
                lanzados += 1
    finally:
        db.close()
    return {"lanzados": lanzados}


@celery_app.task(name="discogs.orders_poll")
def orders_poll() -> dict:
    """Cada 5 min: por cada tenant con Discogs activo (tras la carga inicial) cuyo sondeo toque según su
    frecuencia, baja los pedidos nuevos o modificados. Es solo lectura hacia Discogs, así que también
    funciona con el modo solo lectura; lo que cambia es la app (pedido creado, stock descontado)."""
    db = SessionLocal()
    resultados = {}
    try:
        for tenant in db.scalars(select(Tenant).where(Tenant.activo.is_(True))).all():
            with scoped_to(db, tenant.id):
                config = db.scalar(select(ConfiguracioBotiga))
                if not config or not config.discogs_habilitat or adopcio_feta(db) is None:
                    continue
                settings = get_settings(db)
                db.commit()
                if not settings.orders_auto or not is_due(settings):
                    continue
                try:
                    resultados[str(tenant.id)] = pull_orders(db, tenant)
                except OrdersPullError as exc:
                    db.rollback()
                    log.warning("discogs.orders_poll: %s (tenant=%s)", exc, tenant.id)
                    resultados[str(tenant.id)] = {"error": str(exc)}
    finally:
        db.close()
    return resultados

"""Centro de control del canal Discogs (/admin/canals/discogs): resumen, listings por
item, ajustes y registro de actividad. TODO se sirve desde la caché local (items,
`channel_listings`, `channel_events`...): abrir el dashboard no gasta llamadas de la API
de Discogs (límite ~60/min compartido). Ver docs/PLAN_CANAL_DISCOGS.md §4."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import ChannelEvent, Order, OrderOrigen, OrderStatus, User
from ...models.channels import EVENT_ERROR
from ...services import channel_reconciler as rec
from ...services import channel_alerts, channel_apply, channel_notifications, channel_runs, discogs_jobs as jobs
from ...services.channel_settings import get_settings, serialize, update_settings
from ...services.discogs import is_read_only
from ...services.discogs_sync import adopcio_feta, get_discogs_token_if_enabled
from ...services.security import require_admin
from ...tasks.discogs import audit as audit_task
from ...tasks.discogs import reconcile_apply
from ._shared import require_discogs_enabled

router = APIRouter(
    prefix="/admin/channels/discogs", tags=["admin"],
    dependencies=[Depends(require_admin), Depends(require_discogs_enabled)],
)

# Orden de la tabla: primero lo que necesita atención.
_ORDEN_ACCIO = {rec.PUBLICAR: 0, rec.ACTUALITZAR_PREU: 1, rec.RETIRAR: 2, rec.VINCULAR: 3, rec.OK: 4, rec.RES: 5}


def _recargo(db: Session):
    return get_settings(db).recargo_pct


@router.get("/overview")
def overview(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    rows = rec.plan_rows(db, settings.recargo_pct)

    por_estat: dict[str, int] = {}
    por_accio: dict[str, int] = {}
    valor = 0.0
    for r in rows:
        por_estat[r["estat_canal"]] = por_estat.get(r["estat_canal"], 0) + 1
        por_accio[r["accio"]] = por_accio.get(r["accio"], 0) + 1
        if r["estat_canal"] == rec.E_PUBLICAT:
            valor += float(r["published_price"] if r["published_price"] is not None else r["price"])

    ahora = datetime.now(timezone.utc)
    errors_24h = db.scalar(
        select(func.count()).select_from(ChannelEvent)
        .where(ChannelEvent.outcome == EVENT_ERROR, ChannelEvent.created_at > ahora - timedelta(hours=24))
    )
    open_orders = db.scalar(
        select(func.count()).select_from(Order)
        .where(Order.origin == OrderOrigen.discogs, Order.status.in_([OrderStatus.pendiente_pago, OrderStatus.pagado]))
    )
    last_runs = channel_runs.list_runs(db, 1)
    last_run = None
    if last_runs:
        r = last_runs[0]
        last_run = {
            "id": r.id, "kind": r.kind, "status": channel_runs.effective_status(r, jobs.get_job(request.state.tenant.id)),
            "summary": r.summary, "finished_at": r.finished_at,
        }
    return {
        "estat_canal": por_estat, "accions": {k: v for k, v in por_accio.items() if k not in (rec.OK, rec.RES)},
        "items_a_la_venda": len(rows), "valor_publicat": round(valor, 2),
        "errors_24h": errors_24h, "comandes_obertes": open_orders, "alertes_obertes": channel_alerts.open_counts(db),
        "ultima_execucio": last_run, "settings": serialize(settings),
    }


@router.get("/listings")
def listings(
    estat: str | None = None, accio: str | None = None, condicio: str | None = None, q: str | None = None,
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db),
):
    rows = rec.plan_rows(db, _recargo(db))
    if condicio:
        rows = [r for r in rows if r["condicio"] == condicio]
    if q and q.strip():
        needle = q.strip().lower()
        rows = [
            r for r in rows
            if needle in f"{r['artista'] or ''} {r['titol'] or ''} {r['external_id'] or ''} {r['discogs_release_id'] or ''}".lower()
        ]
    # Los recuentos (para los filtros) se calculan antes de aplicar estat/accio.
    counts_estat: dict[str, int] = {}
    counts_accio: dict[str, int] = {}
    for r in rows:
        counts_estat[r["estat_canal"]] = counts_estat.get(r["estat_canal"], 0) + 1
        counts_accio[r["accio"]] = counts_accio.get(r["accio"], 0) + 1
    if estat:
        rows = [r for r in rows if r["estat_canal"] == estat]
    if accio:
        rows = [r for r in rows if r["accio"] == accio]
    rows.sort(key=lambda r: (_ORDEN_ACCIO.get(r["accio"], 9), (r["artista"] or "").lower(), (r["titol"] or "").lower()))
    return {
        "total": len(rows), "counts_estat": counts_estat, "counts_accio": counts_accio,
        "rows": rows[offset: offset + limit],
    }


class SettingsIn(BaseModel):
    publicacion_auto: bool | None = None
    sync_auto: bool | None = None
    recargo_pct: float | None = Field(None, ge=0, le=100)
    orders_auto: bool | None = None
    orders_poll_minutes: int | None = Field(None, ge=5, le=240)


@router.get("/settings")
def read_settings(db: Session = Depends(get_db)):
    row = get_settings(db)
    db.commit()  # puede haber creado la fila con los valores por defecto
    return serialize(row)


@router.put("/settings")
def write_settings(payload: SettingsIn, db: Session = Depends(get_db)):
    row = update_settings(db, payload.model_dump(exclude_unset=True))
    db.commit()
    return serialize(row)


@router.get("/events")
def events(
    outcome: str | None = None, action: str | None = None, limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0), db: Session = Depends(get_db),
):
    stmt = select(ChannelEvent)
    count_stmt = select(func.count()).select_from(ChannelEvent)
    for col, value in ((ChannelEvent.outcome, outcome), (ChannelEvent.action, action)):
        if value:
            stmt, count_stmt = stmt.where(col == value), count_stmt.where(col == value)
    items = db.scalars(stmt.order_by(ChannelEvent.created_at.desc()).limit(limit).offset(offset)).all()
    return {
        "total": db.scalar(count_stmt),
        "events": [
            {
                "id": e.id, "action": e.action, "outcome": e.outcome, "item_id": e.item_id, "order_id": e.order_id,
                "external_id": e.external_id, "actor": e.actor, "detail": e.detail, "error": e.error,
                "created_at": e.created_at,
            }
            for e in items
        ],
    }


class ReconcileIn(BaseModel):
    actions: list[Literal["publicar", "actualitzar_preu", "retirar"]] | None = None
    item_ids: list[uuid.UUID] | None = None
    force: bool = False


def _selection(db: Session, payload: ReconcileIn):
    settings = get_settings(db)
    plan = rec.plan_rows(db, settings.recargo_pct)
    todo = channel_apply.select_rows(
        plan, set(payload.actions) if payload.actions else None,
        set(payload.item_ids) if payload.item_ids else None,
    )
    return plan, todo


@router.post("/reconcile/preview")
def reconcile_preview(payload: ReconcileIn, db: Session = Depends(get_db)):
    """Qué haría aplicar la reconciliación con esta selección: recuento por acción, muestra y si
    el freno de seguridad la pararía. No toca nada (ni la BD ni Discogs)."""
    plan, todo = _selection(db, payload)
    counts: dict[str, int] = {}
    for r in todo:
        counts[r["accio"]] = counts.get(r["accio"], 0) + 1
    return {
        "total": len(todo), "counts": counts, "sample": todo[:20],
        "guard": channel_apply.retire_guard_message(plan, todo),
    }


@router.post("/reconcile", status_code=202)
def reconcile(
    payload: ReconcileIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    """Aplica la reconciliación en Discogs (publicar, actualizar precio, retirar) como trabajo en
    segundo plano. Exige lectura/escritura; el seguimiento es el mismo que el de las sincronizaciones
    (`/admin/discogs/inventory/jobs/current`)."""
    tenant_id = request.state.tenant.id
    token = get_discogs_token_if_enabled(db, tenant_id)
    if token is None:
        raise HTTPException(409, "No hi ha cap token de Discogs configurat (Configuració).")
    if is_read_only(token):
        raise HTTPException(
            409, "Mode només lectura: desactiva'l a Configuració per poder escriure a Discogs.",
        )
    _, todo = _selection(db, payload)
    if not todo:
        raise HTTPException(409, "No hi ha res a fer amb aquesta selecció.")

    try:
        job = jobs.start_job(tenant_id, "reconcile", {
            "actions": payload.actions, "item_ids": [str(i) for i in payload.item_ids] if payload.item_ids else None,
            "force": payload.force, "actor": admin.email,
        })
    except (jobs.JobConflict, jobs.JobPrecondition) as exc:
        raise HTTPException(409, str(exc))

    channel_runs.create_run(db, job)
    try:
        reconcile_apply.delay(str(tenant_id), job["id"])
    except Exception as exc:  # noqa: BLE001
        jobs.update_job(tenant_id, job["id"], status="error", error=f"No s'ha pogut encuar el treball: {exc}")
        channel_runs.update_run(db, job["id"], status="error", error=f"No s'ha pogut encuar el treball: {exc}")
        raise HTTPException(503, "No s'ha pogut llançar el treball en segon pla (cua no disponible).")
    return {"job": job}


# --- Alertas -----------------------------------------------------------------------------

def _alert_out(a) -> dict:
    return {
        "id": a.id, "kind": a.kind, "severity": a.severity, "message": a.message, "detail": a.detail,
        "item_id": a.item_id, "order_id": a.order_id, "external_id": a.external_id, "status": a.status,
        "occurrences": a.occurrences, "created_at": a.created_at, "updated_at": a.updated_at,
        "resolved_at": a.resolved_at,
    }


@router.get("/alerts")
def alerts(
    status: Literal["open", "resolved", "dismissed", "all"] = "open", kind: str | None = None,
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db),
):
    total, rows = channel_alerts.list_alerts(
        db, status=None if status == "all" else status, kind=kind, limit=limit, offset=offset,
    )
    return {"total": total, "alerts": [_alert_out(a) for a in rows], "open": channel_alerts.open_counts(db)}


class AlertAction(BaseModel):
    action: Literal["resolve", "dismiss", "reopen"]


@router.post("/alerts/{alert_id}")
def alert_action(alert_id: uuid.UUID, payload: AlertAction, db: Session = Depends(get_db)):
    status = {"resolve": "resolved", "dismiss": "dismissed", "reopen": "open"}[payload.action]
    alert = channel_alerts.set_status(db, alert_id, status)
    if alert is None:
        raise HTTPException(404, "Alerta no trobada")
    db.commit()
    return _alert_out(alert)


# --- Avisos (preferencias del usuario) -----------------------------------------------------

@router.get("/notifications")
def notification_prefs(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    prefs = channel_notifications.get_prefs(db, admin.id)
    return {"events": [{**e, "enabled": prefs[e["key"]]} for e in channel_notifications.EVENTS]}


class NotificationPrefsIn(BaseModel):
    prefs: dict[str, bool]


@router.put("/notifications")
def update_notification_prefs(
    payload: NotificationPrefsIn, db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    desconocidos = set(payload.prefs) - channel_notifications.EVENT_KEYS
    if desconocidos:
        raise HTTPException(422, f"Esdeveniments desconeguts: {sorted(desconocidos)}")
    channel_notifications.set_prefs(db, admin.id, payload.prefs)
    db.commit()
    return notification_prefs(db, admin)


# --- Auditoría contra el inventario real ---------------------------------------------------

@router.post("/audit", status_code=202)
def start_audit(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Compara lo que la app cree publicado con el inventario REAL de Discogs y genera alertas.
    Solo lee de Discogs, así que funciona también en modo solo lectura. Exige la carga inicial hecha."""
    tenant_id = request.state.tenant.id
    if get_discogs_token_if_enabled(db, tenant_id) is None:
        raise HTTPException(409, "No hi ha cap token de Discogs configurat (Configuració).")
    if adopcio_feta(db) is None:
        raise HTTPException(409, "Fes primer la càrrega inicial: abans no hi ha res fiable amb què comparar.")
    try:
        job = jobs.start_job(tenant_id, "audit", {"actor": admin.email})
    except (jobs.JobConflict, jobs.JobPrecondition) as exc:
        raise HTTPException(409, str(exc))
    channel_runs.create_run(db, job)
    try:
        audit_task.delay(str(tenant_id), job["id"])
    except Exception as exc:  # noqa: BLE001
        jobs.update_job(tenant_id, job["id"], status="error", error=f"No s'ha pogut encuar el treball: {exc}")
        channel_runs.update_run(db, job["id"], status="error", error=f"No s'ha pogut encuar el treball: {exc}")
        raise HTTPException(503, "No s'ha pogut llançar el treball en segon pla (cua no disponible).")
    return {"job": job}

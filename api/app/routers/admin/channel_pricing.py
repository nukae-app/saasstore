"""Pestaña Preus del centro de control de Discogs: precios sugeridos y de mercado, comisión y reprecio
a partir de la sugerencia de Discogs. Todo es LECTURA de Discogs (funciona en modo solo lectura);
aplicar un reprecio cambia el precio en la APP, no en Discogs (eso lo hace después la reconciliación).
Ver services/channel_pricing.py y docs/PLAN_CANAL_DISCOGS.md."""

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import ChannelSyncRun, User
from ...services import catalog_backup, channel_pricing, channel_runs, discogs_jobs as jobs
from ...services.discogs_sync import get_discogs_token_if_enabled
from ...services.security import require_admin
from ...tasks.discogs import pricing_preview
from ._shared import require_discogs_enabled

router = APIRouter(
    prefix="/admin/channels/discogs/pricing", tags=["admin"],
    dependencies=[Depends(require_admin), Depends(require_discogs_enabled)],
)


def _token(db: Session, request: Request) -> str:
    token = get_discogs_token_if_enabled(db, request.state.tenant.id)
    if token is None:
        raise HTTPException(409, "No hi ha cap token de Discogs configurat (Configuració).")
    return token


@router.get("/release/{release_id}")
def release_market(release_id: int, request: Request, db: Session = Depends(get_db)):
    """Sugerencias por estado + estadísticas de mercado de un release (caché de 6 h)."""
    token = _token(db, request)
    try:
        return channel_pricing.market_for_release(token, release_id)
    except channel_pricing.PricingAbort as exc:
        raise HTTPException(409, str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Error consultant Discogs: {exc}")


@router.get("/fee")
def fee(request: Request, price: float = Query(gt=0, le=100000), db: Session = Depends(get_db)):
    token = _token(db, request)
    try:
        return channel_pricing.fee_for(token, price)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Error consultant Discogs: {exc}")


class PreviewIn(BaseModel):
    item_ids: list[uuid.UUID] | None = None
    limit: int = Field(200, ge=1, le=channel_pricing.MAX_PREVIEW_ITEMS)
    factor: float = Field(1.0, gt=0, le=3)
    step: float = Field(0.5, ge=0, le=10)
    min_diff_pct: float = Field(5.0, ge=0, le=100)


@router.post("/preview", status_code=202)
def start_preview(payload: PreviewIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Lanza (en segundo plano) la consulta de precios sugeridos de los items a la venta y propone un
    precio por item. No cambia nada; el seguimiento es el de los demás trabajos (jobs/current)."""
    tenant_id = request.state.tenant.id
    _token(db, request)
    try:
        job = jobs.start_job(tenant_id, "pricing_preview", {
            "item_ids": [str(i) for i in payload.item_ids] if payload.item_ids else None, "limit": payload.limit,
            "factor": payload.factor, "step": payload.step, "min_diff_pct": payload.min_diff_pct, "actor": admin.email,
        })
    except (jobs.JobConflict, jobs.JobPrecondition) as exc:
        raise HTTPException(409, str(exc))
    channel_runs.create_run(db, job)
    try:
        pricing_preview.delay(str(tenant_id), job["id"])
    except Exception as exc:  # noqa: BLE001
        jobs.update_job(tenant_id, job["id"], status="error", error=f"No s'ha pogut encuar el treball: {exc}")
        channel_runs.update_run(db, job["id"], status="error", error=f"No s'ha pogut encuar el treball: {exc}")
        raise HTTPException(503, "No s'ha pogut llançar el treball en segon pla (cua no disponible).")
    return {"job": job}


class ApplyIn(BaseModel):
    job_id: str
    item_ids: list[uuid.UUID] | None = None  # None = todos los que proponían cambio


@router.post("/apply")
def apply_preview(payload: ApplyIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Aplica en la app los precios propuestos por una vista previa (los elegidos). Salta los items cuyo
    precio cambió desde entonces. Después, "Listings" propone propagar el precio a Discogs."""
    run = db.get(ChannelSyncRun, payload.job_id)
    if run is None or run.kind != "pricing_preview" or run.status != "done":
        raise HTTPException(404, "Simulació de preus no trobada o encara no acabada.")
    rows = jobs.load_rows(request.state.tenant.id, payload.job_id) or channel_runs.load_report(db, payload.job_id) or []
    selected = {str(i) for i in payload.item_ids} if payload.item_ids else None
    # Punto de restauración automático: cambiar precios en bloque se puede deshacer desde Còpies de seguretat.
    catalog_backup.create_snapshot(db, label="Abans d'aplicar preus de Discogs", trigger="pre_prices", actor=admin.email)
    db.commit()
    result = channel_pricing.apply_prices(db, rows, selected, admin.email)
    db.commit()
    return result

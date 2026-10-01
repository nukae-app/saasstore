"""Còpies de seguretat del catàleg i de Discogs (Configuració del canal Discogs).

- Còpia del CATÀLEG de la tenda (releases, items, vincles amb Discogs, listings): permet restaurar el catàleg.
  Mai de tota la base de dades. Restaurar calcula primer què canviaria (vista prèvia) i no toca el que ja no és
  segur (vendes, reserves, comandes posteriors a la còpia). Veure services/catalog_backup.py.
- Còpia de l'inventari i comandes de DISCOGS: només consulta i descàrrega (és lectura de Discogs).
"""

import gzip
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import ChannelBackup, User
from ...models.channels import BACKUP_CATALOG, BACKUP_DISCOGS
from ...services import catalog_backup, channel_runs, discogs_backup, discogs_jobs as jobs
from ...services.discogs_sync import get_discogs_token_if_enabled
from ...services.security import require_admin
from ...tasks.discogs import backup as backup_task
from ._shared import require_discogs_enabled

router = APIRouter(
    prefix="/admin/channels/discogs/backups", tags=["admin"],
    dependencies=[Depends(require_admin), Depends(require_discogs_enabled)],
)


def _out(b: ChannelBackup) -> dict:
    return {
        "id": b.id, "kind": b.kind, "trigger": b.trigger, "label": b.label, "summary": b.summary,
        "size_bytes": b.size_bytes, "created_by": b.created_by, "created_at": b.created_at,
    }


def _get_or_404(db: Session, backup_id: str) -> ChannelBackup:
    b = db.get(ChannelBackup, backup_id)
    if b is None:
        raise HTTPException(404, "Còpia no trobada")
    return b


@router.get("")
def list_backups(kind: str | None = Query(None, pattern="^(catalog|discogs_inventory)$"), db: Session = Depends(get_db)):
    stmt = select(ChannelBackup).order_by(ChannelBackup.created_at.desc()).limit(100)
    if kind:
        stmt = stmt.where(ChannelBackup.kind == kind)
    return [_out(b) for b in db.scalars(stmt).all()]


class CatalogBackupIn(BaseModel):
    label: str | None = None


@router.post("/catalog", status_code=201)
def create_catalog_backup(payload: CatalogBackupIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Punt de restauració del catàleg ara mateix (només de la teva tenda)."""
    label = (payload.label or "").strip()[:200] or None
    b = catalog_backup.create_snapshot(db, label=label, trigger="manual", actor=admin.email)
    db.commit()
    return _out(b)


class DiscogsBackupIn(BaseModel):
    orders: bool = True


@router.post("/discogs", status_code=202)
def start_discogs_backup(
    payload: DiscogsBackupIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    """Còpia de l'inventari (i comandes) de Discogs, en segon pla. Només llegeix de Discogs: funciona també
    en mode només lectura. El seguiment és el dels altres treballs (jobs/current)."""
    tenant_id = request.state.tenant.id
    if get_discogs_token_if_enabled(db, tenant_id) is None:
        raise HTTPException(409, "No hi ha cap token de Discogs configurat (Configuració).")
    try:
        job = jobs.start_job(tenant_id, "discogs_backup", {"orders": payload.orders, "actor": admin.email})
    except (jobs.JobConflict, jobs.JobPrecondition) as exc:
        raise HTTPException(409, str(exc))
    channel_runs.create_run(db, job)
    try:
        backup_task.delay(str(tenant_id), job["id"])
    except Exception as exc:  # noqa: BLE001
        jobs.update_job(tenant_id, job["id"], status="error", error=f"No s'ha pogut encuar el treball: {exc}")
        channel_runs.update_run(db, job["id"], status="error", error=f"No s'ha pogut encuar el treball: {exc}")
        raise HTTPException(503, "No s'ha pogut llançar el treball en segon pla (cua no disponible).")
    return {"job": job}


@router.get("/{backup_id}/download")
def download(
    backup_id: str, request: Request, formato: str = Query("json", pattern="^(json|csv)$"), db: Session = Depends(get_db),
):
    b = _get_or_404(db, backup_id)
    slug = request.state.tenant.slug
    dia = b.created_at.strftime("%Y%m%d-%H%M")
    if formato == "csv":
        if b.kind != BACKUP_DISCOGS:
            raise HTTPException(422, "El CSV només existeix per a les còpies de l'inventari de Discogs.")
        body = discogs_backup.inventory_csv(json.loads(gzip.decompress(b.payload))).encode("utf-8")
        return Response(body, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="discogs_inventari_{slug}_{dia}.csv"'})
    nombre = "cataleg" if b.kind == BACKUP_CATALOG else "discogs"
    return Response(b.payload, media_type="application/gzip",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}_{slug}_{dia}.json.gz"'})


@router.delete("/{backup_id}", status_code=204)
def delete_backup(backup_id: str, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, backup_id))
    db.commit()


def _require_catalog(b: ChannelBackup) -> None:
    if b.kind != BACKUP_CATALOG:
        raise HTTPException(422, "Només es poden restaurar les còpies del catàleg.")


def _no_job_running(request: Request) -> None:
    job = jobs.get_job(request.state.tenant.id)
    if job and job["status"] in ("queued", "running"):
        raise HTTPException(409, "Hi ha un treball en marxa: espera que acabi abans de restaurar.")


@router.post("/{backup_id}/restore/preview")
def restore_preview(backup_id: str, db: Session = Depends(get_db)):
    """Què canviaria restaurar aquesta còpia (i quins items es deixarien per conflicte). No modifica res."""
    b = _get_or_404(db, backup_id)
    _require_catalog(b)
    return catalog_backup.preview(db, b)


class RestoreIn(BaseModel):
    confirm: bool = False


@router.post("/{backup_id}/restore")
def restore(
    backup_id: str, payload: RestoreIn, request: Request, db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Restaura el catàleg a l'estat d'aquesta còpia (excepte els conflictes). Abans en guarda una còpia automàtica
    de l'estat actual, i tot es fa en una sola transacció."""
    if not payload.confirm:
        raise HTTPException(422, "Cal confirmar la restauració (confirm=true).")
    b = _get_or_404(db, backup_id)
    _require_catalog(b)
    _no_job_running(request)
    try:
        return catalog_backup.restore(db, b, actor=admin.email)
    except catalog_backup.RestoreError as exc:
        raise HTTPException(500, str(exc))

"""Pantalla /admin/canals/discogs: sincronització d'inventari Discogs -> app.

Dos passos: una SIMULACIÓ (dry-run, no guarda res) que es revisa, i una
EXECUCIÓ REAL que només es permet si hi ha una simulació de menys de 24 h.
Tot corre en segon pla (Celery, ~1,1 s per crida a Discogs) i aquí només es
llança, es consulta el progrés i es llegeix l'informe. Només BAIXA dades de
Discogs, així que no li afecta el mode "només lectura" (que bloqueja escriure-hi).
Vegeu services/discogs_inventory_sync.py i docs/PLAN_CANAL_DISCOGS.md §8."""

import csv
import io
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...services import discogs_jobs as jobs
from ...services.discogs_inventory_sync import INFORME_COLUMNES
from ...services.discogs_sync import adopcio_feta, resolve_discogs_token
from ...services.security import require_admin
from ...tasks.discogs import inventory_sync
from ...tenant_secrets import get_tenant_secrets
from ._shared import require_discogs_enabled

router = APIRouter(
    prefix="/admin/discogs/inventory", tags=["admin"],
    dependencies=[Depends(require_admin), Depends(require_discogs_enabled)],
)


class InventoryJobIn(BaseModel):
    mode: Literal["dry_run", "apply"]
    limit: int = Field(0, ge=0, le=100_000, description="només N listings (proves); no retira res")
    force: bool = False
    reobrir_adopcio: bool = False


def _estat(tenant_id, job: dict | None) -> dict:
    """Treball actual + context que la pantalla necessita per decidir què mostrar."""
    dry = jobs.last_dry_run(tenant_id)
    return {"job": job, "ultima_simulacio": dry}


@router.post("/jobs", status_code=202)
def start_inventory_job(payload: InventoryJobIn, request: Request, db: Session = Depends(get_db)):
    tenant_id = request.state.tenant.id
    if not resolve_discogs_token(get_tenant_secrets(tenant_id)):
        raise HTTPException(409, "El tenant no té cap token de Discogs configurat (Configuració).")
    if payload.mode == "apply" and adopcio_feta(db) is not None and not payload.reobrir_adopcio:
        raise HTTPException(409, "L'adopció inicial ja està feta: l'app és la font de veritat.")

    try:
        job = jobs.start_job(
            tenant_id, payload.mode,
            {"limit": payload.limit, "force": payload.force, "reobrir_adopcio": payload.reobrir_adopcio},
        )
    except jobs.JobConflict as exc:
        raise HTTPException(409, str(exc))
    except jobs.JobPrecondition as exc:
        raise HTTPException(409, str(exc))

    try:
        inventory_sync.delay(str(tenant_id), job["id"])
    except Exception as exc:  # noqa: BLE001 — broker caigut: que es vegi, no un treball fantasma
        jobs.update_job(tenant_id, job["id"], status="error", error=f"No s'ha pogut encuar el treball: {exc}")
        raise HTTPException(503, "No s'ha pogut llançar el treball en segon pla (cua no disponible).")
    return _estat(tenant_id, job)


@router.get("/jobs/current")
def current_inventory_job(request: Request):
    tenant_id = request.state.tenant.id
    return _estat(tenant_id, jobs.get_job(tenant_id))


def _rows_or_404(tenant_id, job_id: str) -> list[dict]:
    rows = jobs.load_rows(tenant_id, job_id)
    if rows is None:
        raise HTTPException(404, "Informe no trobat (potser ha caducat).")
    return rows


@router.get("/jobs/{job_id}/rows")
def inventory_job_rows(
    job_id: str, request: Request, accio: str | None = None, q: str | None = None,
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
):
    rows = _rows_or_404(request.state.tenant.id, job_id)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["accio"]] = counts.get(r["accio"], 0) + 1

    if accio:
        rows = [r for r in rows if r["accio"] == accio]
    if q:
        needle = q.lower()
        rows = [
            r for r in rows
            if needle in f"{r.get('artista') or ''} {r.get('titol') or ''} {r.get('codi_discogs') or ''}".lower()
        ]
    return {"total": len(rows), "counts": counts, "rows": rows[offset: offset + limit]}


@router.get("/jobs/{job_id}/report.csv")
def inventory_job_report(job_id: str, request: Request):
    rows = _rows_or_404(request.state.tenant.id, job_id)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=INFORME_COLUMNES)
    w.writeheader()
    w.writerows(rows)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="discogs_inventari_{job_id[:8]}.csv"'},
    )

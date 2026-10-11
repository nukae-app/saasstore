"""Pestaña "Vincular" del centro de control de Discogs: cola de releases con stock activo y sin
`discogs_release_id`, búsqueda de candidatos (EAN primero) y vinculación. Solo lee de Discogs, así
que no depende del modo solo lectura. Ver services/discogs_link.py."""

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import Item, RecordProduct, Release, User
from ...services import discogs, discogs_link as link
from ...services.discogs_sync import get_discogs_token_if_enabled
from ...services.security import require_admin
from ._shared import require_discogs_enabled

router = APIRouter(
    prefix="/admin/channels/discogs/vincular", tags=["admin"],
    dependencies=[Depends(require_admin), Depends(require_discogs_enabled)],
)


def _get_release(db: Session, release_id: uuid.UUID) -> Release:
    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(404, "Release no trobat")
    if release.discogs_release_id:
        raise HTTPException(409, "El release ja està vinculat a Discogs")
    return release


def _row(r: Release, num_items: int) -> dict:
    rec = r.record
    return {
        "release_id": r.id, "artista": r.artista, "titulo": r.title, "formato": r.formato, "sello": r.sello,
        "ean": r.ean, "imagen_url": r.image_url, "num_items": num_items,
        "ajornat": bool(rec and rec.discogs_link_skipped),
        "ultima_cerca": rec.discogs_link_checked_at if rec else None,
    }


@router.get("")
def vincular_cua(
    filtre: str = Query("pendents", pattern="^(pendents|amb_ean|sense_ean|ajornats)$"),
    q: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    base = link.pending_stmt()
    if q and q.strip():
        like = f"%{q.strip()}%"
        base = base.where(or_(Release.title.ilike(like), RecordProduct.artista.ilike(like), Release.ean.ilike(like)))
    # Recuentos para los filtros, antes de aplicar `filtre`.
    todos = db.scalars(base.options(selectinload(Release.record)).order_by(Release.title)).all()
    counts = {
        "pendents": sum(1 for r in todos if not (r.record and r.record.discogs_link_skipped)),
        "ajornats": sum(1 for r in todos if r.record and r.record.discogs_link_skipped),
        "amb_ean": sum(1 for r in todos if r.ean and not (r.record and r.record.discogs_link_skipped)),
        "sense_ean": sum(1 for r in todos if not r.ean and not (r.record and r.record.discogs_link_skipped)),
    }
    if filtre == "ajornats":
        rows = [r for r in todos if r.record and r.record.discogs_link_skipped]
    else:
        rows = [r for r in todos if not (r.record and r.record.discogs_link_skipped)]
        if filtre == "amb_ean":
            rows = [r for r in rows if r.ean]
        elif filtre == "sense_ean":
            rows = [r for r in rows if not r.ean]
    page = rows[offset: offset + limit]
    n_items = dict(db.execute(
        select(Item.release_id, func.count()).where(
            Item.release_id.in_([r.id for r in page]), Item.status.in_(link.ACTIVE),
        ).group_by(Item.release_id)
    ).all()) if page else {}
    return {"total": len(rows), "counts": counts, "rows": [_row(r, n_items.get(r.id, 0)) for r in page]}


@router.get("/prova")
def vincular_prova(request: Request, ean: str = Query(min_length=1), db: Session = Depends(get_db)):
    """Diagnóstico (pestaña "Prova API"): ejecuta UNA búsqueda por código de barras contra Discogs y
    devuelve el estado HTTP crudo y los resultados parseados. No guarda nada."""
    digits = link.clean_ean(ean)
    if not digits:
        raise HTTPException(422, "EAN no vàlid")
    token = get_discogs_token_if_enabled(db, request.state.tenant.id)
    if token is None:
        raise HTTPException(422, "Discogs sense token configurat")
    discogs._throttle()
    try:
        with discogs._client(token) as c:
            r = c.get("/database/search", params={"barcode": digits, "type": "release", "per_page": 10})
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"No s'ha pogut arribar a Discogs: {exc}")
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    hits = body.get("results", []) if r.is_success else []
    return {
        "ean": digits, "http_status": r.status_code,
        "total_discogs": (body.get("pagination") or {}).get("items"),
        "ratelimit_restant": r.headers.get("X-Discogs-Ratelimit-Remaining"),
        "resultats": discogs._parse_search_hits(hits),
        "error": None if r.is_success else r.text[:300],
    }


@router.get("/{release_id}/candidats")
def vincular_candidats(
    release_id: uuid.UUID, request: Request, q: str | None = None, db: Session = Depends(get_db),
):
    release = _get_release(db, release_id)
    token = get_discogs_token_if_enabled(db, request.state.tenant.id)
    try:
        candidats = link.find_candidates(token, release, q=q)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Error consultant Discogs: {exc}")
    release._ensure_record().discogs_link_checked_at = func.now()
    db.commit()
    return {"ean": release.ean, "candidats": candidats}


@router.post("/auto")
def vincular_auto(
    request: Request, limit: int = Query(15, ge=1, le=40),
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    """Busca por EAN una tanda de pendientes y vincula los de candidato único. Acotada por `limit`
    por el límite de la API de Discogs; repetir hasta que `revisats` sea 0."""
    token = get_discogs_token_if_enabled(db, request.state.tenant.id)
    if token is None:
        raise HTTPException(422, "Discogs sense token configurat")
    return link.auto_link(db, token, limit=limit, actor=admin.email)


class VincularIn(BaseModel):
    discogs_release_id: int
    force: bool = False


@router.post("/{release_id}")
def vincular_release(
    release_id: uuid.UUID, payload: VincularIn, request: Request,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    release = _get_release(db, release_id)
    token = get_discogs_token_if_enabled(db, request.state.tenant.id)
    try:
        enriched = link.link_release(
            db, release, payload.discogs_release_id, token, actor=admin.email, via="manual", force=payload.force,
        )
    except link.LinkConflict as exc:
        raise HTTPException(409, {
            "message": "Aquest ID de Discogs ja el té un altre release.",
            "release_id": str(exc.other.id), "artista": exc.other.artista, "titulo": exc.other.title,
        })
    return {"id": release.id, "discogs_release_id": release.discogs_release_id, "enriquit": enriched}


class AjornarIn(BaseModel):
    ajornat: bool = True


@router.post("/{release_id}/ajornar")
def vincular_ajornar(release_id: uuid.UUID, payload: AjornarIn, db: Session = Depends(get_db)):
    release = _get_release(db, release_id)
    link.mark_skipped(db, release, payload.ajornat)
    return {"id": release.id, "ajornat": payload.ajornat}

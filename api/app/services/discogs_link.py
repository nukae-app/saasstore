"""Cola "Vincular" del canal Discogs: releases con stock activo y sin `discogs_release_id`
(típicamente altas a mano de novedades que aún no estaban en Discogs).

Solo LEE de Discogs (búsquedas y ficha), así que funciona también en modo solo lectura.
Vincular NO publica nada: el release pasa a "pendent" en Listings y la publicación sigue su
propio flujo (vista previa / aprobación). La vinculación automática solo se hace con un
candidato ÚNICO por EAN; todo lo demás queda para revisar a mano.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session, selectinload

from ..models import Item, ItemStatus, RecordProduct, Release
from . import discogs
from .channel_events import record_event
from .discogs_sync import enrich_release_from_discogs

log = logging.getLogger(__name__)

RECHECK_HOURS = 24
ACTIVE = (ItemStatus.disponible, ItemStatus.reservado)


class LinkConflict(Exception):
    """El discogs_release_id ya lo tiene otro release del catálogo."""

    def __init__(self, other: Release):
        super().__init__(f"Ja vinculat al release {other.id}")
        self.other = other


def clean_ean(value: str | None) -> str | None:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    return digits or None


def pending_stmt():
    """Releases con algún item activo y sin vincular."""
    return (
        select(Release)
        .outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
        .where(RecordProduct.discogs_release_id.is_(None))
        .where(exists().where(Item.release_id == Release.id, Item.status.in_(ACTIVE)))
    )


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def find_candidates(token: str | None, release: Release, q: str | None = None) -> list[dict]:
    """Candidatos de Discogs. Primero por EAN (fiable); si no hay EAN o no devuelve nada, por
    texto (artista + título, o `q` si se pasa). Cada candidato lleva `via` ('ean'|'text') y, en
    texto, `exacte` si artista y título coinciden exactamente."""
    ean = clean_ean(release.ean)
    if ean and not q:
        hits = discogs.search_by_barcode(token, ean)
        if hits:
            return [{**h, "via": "ean", "exacte": True} for h in hits]
    text = (q or f"{release.artista or ''} {release.title or ''}").strip()
    if not text:
        return []
    out = []
    for h in discogs.search_releases(token, text):
        exacte = _norm(h.get("artista")) == _norm(release.artista) and _norm(h.get("titulo")) == _norm(release.title)
        out.append({**h, "via": "text", "exacte": exacte})
    return out


def link_release(
    db: Session, release: Release, discogs_release_id: int, token: str | None, *,
    actor: str | None = None, via: str = "manual", force: bool = False,
) -> bool:
    """Fija el discogs_release_id y enriquece la ficha. Devuelve si el enriquecimiento ha ido bien
    (el vínculo se guarda igualmente). Aixeca LinkConflict si otro release ya lo usa (salvo `force`)."""
    if not force:
        other = db.scalar(
            select(Release)
            .join(RecordProduct, RecordProduct.release_id == Release.id)
            .where(RecordProduct.discogs_release_id == discogs_release_id, Release.id != release.id)
        )
        if other is not None:
            raise LinkConflict(other)
    release.discogs_release_id = discogs_release_id
    release._ensure_record().discogs_link_skipped = False
    release._ensure_record().discogs_link_checked_at = datetime.now(timezone.utc)
    record_event(
        db, "link", "ok", actor=actor, external_id=discogs_release_id,
        detail={"release_id": str(release.id), "via": via, "titulo": release.title},
    )
    db.flush()
    enriched = enrich_release_from_discogs(release, db, token)  # hace commit
    db.commit()
    return enriched


def mark_skipped(db: Session, release: Release, skipped: bool) -> None:
    release._ensure_record().discogs_link_skipped = skipped
    db.commit()


def auto_link(db: Session, token: str | None, *, limit: int = 20, actor: str | None = None) -> dict:
    """Busca por EAN los releases pendientes (con EAN, no aplazados, no mirados en las últimas
    RECHECK_HOURS) y vincula los que tienen un único candidato. Pensado para el reintento periódico
    y para el botón de la pestaña: `limit` acota las llamadas a Discogs (~60/min)."""
    limite = datetime.now(timezone.utc) - timedelta(hours=RECHECK_HOURS)
    stmt = (
        pending_stmt()
        .options(selectinload(Release.record))
        .where(Release.ean.is_not(None), Release.ean != "")
        .where(or_(RecordProduct.discogs_link_skipped.is_(None), RecordProduct.discogs_link_skipped.is_(False)))
        .where(or_(RecordProduct.discogs_link_checked_at.is_(None), RecordProduct.discogs_link_checked_at < limite))
        .order_by(RecordProduct.discogs_link_checked_at.asc().nullsfirst())
        .limit(limit)
    )
    res = {"revisats": 0, "vinculats": 0, "ambigus": 0, "sense_resultat": 0, "errors": 0, "aturat": None}
    for release in db.scalars(stmt).all():
        ean = clean_ean(release.ean)
        if not ean:
            continue
        res["revisats"] += 1
        try:
            hits = discogs.search_by_barcode(token, ean)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                res["aturat"] = "Límit de Discogs assolit"
                break
            res["errors"] += 1
            continue
        except Exception:  # noqa: BLE001 — best-effort, el siguiente intento reintenta
            log.warning("discogs_link: error buscando EAN %s", ean, exc_info=True)
            res["errors"] += 1
            continue
        release._ensure_record().discogs_link_checked_at = datetime.now(timezone.utc)
        if len(hits) == 1 and hits[0].get("discogs_release_id"):
            try:
                link_release(db, release, int(hits[0]["discogs_release_id"]), token, actor=actor, via="ean_auto")
                res["vinculats"] += 1
                continue
            except LinkConflict:
                res["ambigus"] += 1
        elif len(hits) > 1:
            res["ambigus"] += 1
        else:
            res["sense_resultat"] += 1
        db.commit()
    return res

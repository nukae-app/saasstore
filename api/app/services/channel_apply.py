"""Aplicador del plan de reconciliación (services/channel_reconciler.py): ESCRIBE en Discogs
para que lo publicado coincida con el stock y los precios de la app (publicar, actualizar
precio, retirar). Lo lanzan el botón de la pestaña Listings y la tarea programada.

Garantías:
- Solo con Discogs activo, token y modo lectura/escritura (el modo solo lectura aborta).
- Freno de seguridad: no retira de golpe más del 20 % de lo publicado (salvo `force`).
- Cada operación deja un evento (channel_events) y actualiza `channel_listings`; mantiene
  también `record_stock_details.codi_discogs`, que el resto de la app sigue usando.
- Primero retira (para no vender lo que ya no hay), luego actualiza precios y al final publica."""

import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CHANNEL_DISCOGS, ChannelListing, CondicionItem, Item, Tenant
from ..models.channels import LISTING_ERROR, LISTING_PUBLICAT, LISTING_RETIRAT
from . import channel_reconciler as rec
from .channel_alerts import raise_alert, resolve_alerts
from .channel_settings import get_settings
from .discogs import is_read_only
from .discogs_inventory_sync import _fila
from .discogs_sync import get_discogs_token_if_enabled, push_listing, remove_listing, update_listing

log = logging.getLogger(__name__)

ACTIONABLE = {rec.RETIRAR, rec.ACTUALITZAR_PREU, rec.PUBLICAR}
_ORDER = {rec.RETIRAR: 0, rec.ACTUALITZAR_PREU: 1, rec.PUBLICAR: 2}
MAX_RETIRE_PCT = 20.0
MIN_RETIRE_FOR_GUARD = 20  # por debajo de este número no tiene sentido frenar por porcentaje
COMMIT_EVERY = 20


class ReconcileAbort(Exception):
    """Salvaguarda que impide ejecutar (mensaje para el usuario)."""


@dataclass
class ReconcileResult:
    rows: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def scheduled_actions(settings) -> set[str]:
    """Qué hace sola la tarea programada: retirar siempre (decisión del plan); publicar y
    actualizar precios solo si la publicación automática está activada."""
    acciones = {rec.RETIRAR}
    if settings.publicacion_auto:
        acciones |= {rec.PUBLICAR, rec.ACTUALITZAR_PREU}
    return acciones


def _listing(db: Session, item: Item) -> ChannelListing | None:
    return db.scalar(
        select(ChannelListing).where(ChannelListing.item_id == item.id, ChannelListing.channel == CHANNEL_DISCOGS)
    )


def _upsert(db: Session, item: Item, listing: ChannelListing | None, **fields) -> ChannelListing:
    from datetime import datetime, timezone

    if listing is None:
        listing = ChannelListing(item_id=item.id, channel=CHANNEL_DISCOGS)
        db.add(listing)
    for key, value in fields.items():
        setattr(listing, key, value)
    listing.last_synced_at = datetime.now(timezone.utc)
    db.flush()
    return listing


def _cond(item: Item) -> str:
    return "M" if item.condition == CondicionItem.nou else (item.estado_disco or "")


def select_rows(
    plan: list[dict], actions: set[str] | None, item_ids: set | None, skip_errors: bool = False,
) -> list[dict]:
    """Filas del plan que se van a ejecutar, en orden de ejecución."""
    wanted = (set(actions) & ACTIONABLE) if actions else set(ACTIONABLE)
    todo = [
        r for r in plan
        if r["accio"] in wanted and (item_ids is None or r["item_id"] in item_ids)
        and not (skip_errors and r["listing_status"] == LISTING_ERROR)
    ]
    todo.sort(key=lambda r: _ORDER[r["accio"]])
    return todo


def retire_guard_message(plan: list[dict], todo: list[dict]) -> str | None:
    """Mensaje si retirar `todo` de golpe supera el freno (más del 20 % de lo publicado)."""
    publicats = sum(1 for r in plan if r["estat_canal"] == rec.E_PUBLICAT)
    retirar_n = sum(1 for r in todo if r["accio"] == rec.RETIRAR)
    if retirar_n > MIN_RETIRE_FOR_GUARD and publicats and 100 * retirar_n / publicats > MAX_RETIRE_PCT:
        return (
            f"S'haurien de retirar {retirar_n} de {publicats} listings publicats "
            f"({100 * retirar_n / publicats:.0f} %, límit {MAX_RETIRE_PCT:g} %). Revisa'ls abans (o força-ho)."
        )
    return None


def run_reconcile(
    db: Session, tenant: Tenant, *, actions: set[str] | None = None, item_ids: set | None = None,
    actor: str | None = None, force: bool = False, skip_errors: bool = False,
    log_fn=print, progress=lambda *a, **k: None,
) -> ReconcileResult:
    """Aplica las acciones elegidas del plan. `skip_errors=True` (tarea programada) deja para
    revisión manual los items cuyo listing quedó en error (p. ej. 404): reintentarlos solos
    podría duplicar un listing de algo ya vendido en Discogs."""
    token = get_discogs_token_if_enabled(db, tenant.id)
    if token is None:
        raise ReconcileAbort("Discogs està desactivat o no hi ha cap token configurat.")
    if is_read_only(token):
        raise ReconcileAbort("Mode només lectura: desactiva'l a Configuració per poder escriure a Discogs.")

    settings = get_settings(db)
    plan = rec.plan_rows(db, settings.recargo_pct)
    wanted = (set(actions) & ACTIONABLE) if actions else set(ACTIONABLE)
    todo = select_rows(plan, actions, item_ids, skip_errors)

    # Freno de seguridad: retirar de golpe una parte grande de lo publicado casi siempre es un error.
    guard = retire_guard_message(plan, todo)
    if guard and not force:
        raise ReconcileAbort(guard)

    filas: list[dict] = []
    ok = {rec.PUBLICAR: 0, rec.ACTUALITZAR_PREU: 0, rec.RETIRAR: 0}
    errors = 0
    total = len(todo)
    log_fn(f"Reconciliació: {total} operacions ({', '.join(sorted(wanted))}).")
    progress("aplicar", 0, total)

    for i, r in enumerate(todo, 1):
        item = db.get(Item, r["item_id"])
        listing = _listing(db, item)
        rid = r["discogs_release_id"]
        target = r["target_price"]
        err = None
        try:
            if r["accio"] == rec.RETIRAR:
                done, err = remove_listing(token, int(listing.external_id), db=db, item_id=item.id, actor=actor)
                if done:
                    if item.codi_discogs == int(listing.external_id):
                        item.codi_discogs = None
                    _upsert(db, item, listing, status=LISTING_RETIRAT, last_error=None)
            elif r["accio"] == rec.ACTUALITZAR_PREU:
                done, err, gone = update_listing(
                    token, int(listing.external_id), item.id, rid, float(target), item.estado_disco,
                    item.estado_funda, es_nou=item.condition == CondicionItem.nou, db=db, actor=actor,
                )
                if done:
                    _upsert(db, item, listing, published_price=target, last_error=None)
                elif gone:
                    _upsert(db, item, listing, status=LISTING_ERROR, last_error="El listing ja no existeix a Discogs (404)")
            else:  # PUBLICAR
                lid, err = push_listing(
                    token, item.id, rid, float(target), item.estado_disco, item.estado_funda,
                    es_nou=item.condition == CondicionItem.nou, db=db, actor=actor,
                )
                done = lid is not None
                if done:
                    item.codi_discogs = lid
                    listing = _upsert(
                        db, item, listing, external_id=str(lid), status=LISTING_PUBLICAT, published_price=target,
                        published_condition=_cond(item), last_error=None,
                    )
                else:
                    _upsert(
                        db, item, listing, status=LISTING_ERROR, last_error=err,
                        attempts=(listing.attempts if listing else 0) + 1,
                    )
        except Exception as exc:  # noqa: BLE001 — un item roto no debe parar el resto
            done, err = False, str(exc)
            log.warning("channel_apply: %s del item %s ha fallat: %s", r["accio"], item.id, exc, exc_info=True)

        common = dict(
            codi=int(listing.external_id) if listing and listing.external_id and listing.external_id.isdigit() else None,
            release_id=rid, artista=r["artista"], titol=r["titol"], condicio=r["condicio"],
            preu_app=r["price"], preu_discogs=target, item_id=item.id,
        )
        ref = f"item:{item.id}"
        if done:
            ok[r["accio"]] += 1
            filas.append(_fila(r["accio"], **common, motiu="OK"))
            resolve_alerts(db, kind="listing_error", ref_key=ref)
        else:
            errors += 1
            filas.append(_fila("error", **common, motiu=f"{r['accio']}: {err}"))
            raise_alert(
                db, "listing_error", ref, f"{r['titol']} ({r['artista'] or '—'}): no s'ha pogut {r['accio']} — {err}",
                severity="error", item_id=item.id, external_id=common["codi"], detail={"accio": r["accio"], "error": err},
            )

        if i % COMMIT_EVERY == 0:
            db.commit()
        if i % 5 == 0 or i == total:
            progress("aplicar", i, total)

    db.commit()
    summary = {
        "mode": "reconcile", "total": total, "publicats": ok[rec.PUBLICAR], "actualitzats": ok[rec.ACTUALITZAR_PREU],
        "retirats": ok[rec.RETIRAR], "errors": errors, "accions": sorted(wanted), "avisos": [],
        "dry_run": False, "actor": actor or "sistema",
    }
    log_fn(
        f"Fet: {summary['publicats']} publicats, {summary['actualitzats']} preus actualitzats, "
        f"{summary['retirats']} retirats, {errors} errors."
    )
    return ReconcileResult(rows=filas, summary=summary)

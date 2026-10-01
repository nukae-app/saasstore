"""Auditoría del canal Discogs: compara LO QUE LA APP CREE que está publicado (`channel_listings`) con el
inventario REAL de Discogs y avisa de las diferencias. Solo LEE de Discogs (GET), así que también
funciona en modo solo lectura, y NO modifica nada: genera alertas (y un informe) que se resuelven a
mano o se cierran solas cuando la diferencia desaparece. Solo tiene sentido tras la carga inicial.

Diferencias:
- `orfe_discogs`: listing en Discogs que la app no conoce (alta hecha en Discogs, o vínculo perdido).
- `no_a_discogs`: la app cree que está publicado pero ya no está en Discogs (vendido allí y aún sin
  traer el pedido, o borrado a mano).
- `preu_diferent`: el precio en Discogs no es el que la app publicó (alguien lo cambió allí)."""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CHANNEL_DISCOGS, ChannelListing, Item, Release, Tenant
from ..models.channels import LISTING_PUBLICAT
from .channel_alerts import raise_alert, resolve_alerts
from .discogs_inventory_sync import InventorySyncResult, _fetch_inventory, _fetch_username, _fila
from .discogs_sync import adopcio_feta, get_discogs_token_if_enabled

log = logging.getLogger(__name__)

MAX_ALERTS_PER_KIND = 200  # el resumen cuenta todo; las alertas individuales se limitan para no inundar


class AuditAbort(Exception):
    """No se puede auditar (mensaje para el usuario)."""


def _noop(*_a, **_k) -> None:
    return None


def run_audit(db: Session, tenant: Tenant, *, log_fn=print, progress=_noop) -> InventorySyncResult:
    token = get_discogs_token_if_enabled(db, tenant.id)
    if token is None:
        raise AuditAbort("Discogs està desactivat o no hi ha cap token configurat.")
    if adopcio_feta(db) is None:
        raise AuditAbort("Fes primer la càrrega inicial: abans no hi ha res fiable amb què comparar.")

    progress("connexio", 0, 0)
    username = _fetch_username(token)
    log_fn(f"Compte Discogs autenticat: {username}")
    listings = _fetch_inventory(token, username, 0, on_page=lambda feta, total: progress("inventari", feta, total))
    en_discogs = {int(l["id"]): l for l in listings}
    log_fn(f"Listings 'For Sale' a Discogs: {len(en_discogs)}")

    locales = {
        int(l.external_id): l
        for l in db.scalars(
            select(ChannelListing).where(ChannelListing.channel == CHANNEL_DISCOGS, ChannelListing.status == LISTING_PUBLICAT)
        ).all()
        if l.external_id and l.external_id.isdigit()
    }

    filas: list[dict] = []
    vistos: dict[str, set[str]] = {"audit_orphan_listing": set(), "audit_missing_listing": set(), "audit_price_diff": set()}
    contadores = {"orfes": 0, "no_a_discogs": 0, "preus": 0}
    progress("comparar", 0, 0)

    for codi, l in en_discogs.items():
        rel = l.get("release") or {}
        precio = Decimal(str((l.get("price") or {}).get("value", 0)))
        local = locales.get(codi)
        if local is None:
            contadores["orfes"] += 1
            ref = f"orphan:{codi}"
            vistos["audit_orphan_listing"].add(ref)
            filas.append(_fila("orfe_discogs", codi=codi, release_id=rel.get("id"), titol=rel.get("description"),
                               preu_discogs=precio, motiu="listing a Discogs que l'app no coneix"))
            if contadores["orfes"] <= MAX_ALERTS_PER_KIND:
                raise_alert(
                    db, "audit_orphan_listing", ref,
                    f"Listing {codi} a Discogs ({rel.get('description')}) que l'app no coneix.",
                    external_id=codi, detail={"price": float(precio), "release_id": rel.get("id")}, notify=False,
                )
        elif local.published_price is not None and Decimal(str(local.published_price)) != precio:
            contadores["preus"] += 1
            ref = f"pricediff:{local.item_id}"
            vistos["audit_price_diff"].add(ref)
            filas.append(_fila("preu_diferent", codi=codi, release_id=rel.get("id"), titol=rel.get("description"),
                               preu_app=local.published_price, preu_discogs=precio, item_id=local.item_id,
                               motiu="el preu a Discogs no és el que l'app va publicar"))
            if contadores["preus"] <= MAX_ALERTS_PER_KIND:
                raise_alert(
                    db, "audit_price_diff", ref,
                    f"Preu diferent a Discogs per {rel.get('description')}: app {local.published_price} € / Discogs {precio} €.",
                    item_id=local.item_id, external_id=codi,
                    detail={"app": float(local.published_price), "discogs": float(precio)}, notify=False,
                )

    for codi, local in locales.items():
        if codi in en_discogs:
            continue
        contadores["no_a_discogs"] += 1
        item = db.get(Item, local.item_id)
        release = db.get(Release, item.release_id) if item else None
        titol = release.title if release else None
        artista = release.artista if release else None
        ref = f"missing:{local.item_id}"
        vistos["audit_missing_listing"].add(ref)
        filas.append(_fila("no_a_discogs", codi=codi, artista=artista, titol=titol, preu_app=local.published_price,
                           item_id=local.item_id,
                           motiu="l'app el creu publicat però ja no és a Discogs (venut allà o esborrat)"))
        if contadores["no_a_discogs"] <= MAX_ALERTS_PER_KIND:
            raise_alert(
                db, "audit_missing_listing", ref,
                f"{titol} ({artista or '—'}): l'app el creu publicat (listing {codi}) però ja no és a Discogs.",
                item_id=local.item_id, external_id=codi, notify=False,
            )

    # Alertas de auditoría cuya diferencia ya no existe: se cierran solas.
    for kind, refs in vistos.items():
        resolve_alerts(db, kind=kind, keep_ref_keys=refs)

    total = sum(contadores.values())
    if total:
        # Un único aviso resumen (no uno por alerta): se encola como una alerta virtual de resumen.
        raise_alert(
            db, "audit_summary", "audit:summary",
            f"L'auditoria ha trobat {total} diferències amb Discogs "
            f"({contadores['orfes']} orfes, {contadores['no_a_discogs']} ja no hi són, {contadores['preus']} de preu).",
            detail=contadores,
        )
    else:
        resolve_alerts(db, ref_key="audit:summary")
    db.commit()

    summary = {
        "mode": "audit", "listings_discogs": len(en_discogs), "publicats_app": len(locales),
        "orfes": contadores["orfes"], "no_a_discogs": contadores["no_a_discogs"], "preus": contadores["preus"],
        "errors": 0, "avisos": [], "dry_run": True, "compte_discogs": username,
    }
    log_fn(f"Auditoria: {contadores['orfes']} orfes, {contadores['no_a_discogs']} ja no hi són, {contadores['preus']} de preu.")
    progress("fet", 0, 0)
    return InventorySyncResult(rows=filas, summary=summary)

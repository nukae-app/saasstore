"""Sincronització de l'inventari de Discogs cap a l'app ("Discogs mana").

Lògica compartida per `scripts/sync_discogs_inventory.py` (CLI) i per la
pantalla d'admin (tasca de Celery, `tasks/discogs.py`): un únic codi, de manera
que la simulació (dry-run) és fidel a l'execució real. Només LLEGEIX de
Discogs (GET); mai crea, edita ni elimina cap listing. Reconcilia la BD
(crea ítems, sincronitza preus, retira el que ja no hi és) — vegeu el docstring
del script per al detall del comportament i de les salvaguardes (informe per
ítem, fre de seguretat, marca d'adopció feta). docs/PLAN_CANAL_DISCOGS.md §8.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from ..models import (
    Assignacio, CartItem, CondicionItem, DevolucionCompra, DevolucionVenta, Item, ItemStatus,
    OrderItem, PeticionCliente, RecordProduct, RecordStockDetail, Release, SolicitudCompraLinea,
    StockHold, Tenant, VentaExterna,
)
from ..tenant_secrets import get_tenant_secrets
from . import discogs
from .catalog_sync import clean, derive_condicion
from .catalog_backup import create_snapshot
from .channel_listings import backfill_discogs_listings
from .discogs_sync import adopcio_feta, marcar_adopcio_feta, resolve_discogs_token


class InventorySyncAbort(Exception):
    """Salvaguarda que atura l'execució abans de tocar res (missatge per a l'usuari)."""


@dataclass
class InventorySyncResult:
    rows: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def _tiene_dependientes(db, item_id) -> bool:
    """Cualquier referencia externa a este item_id (ver docstring del módulo):
    si hay alguna, no se consolida ese release automáticamente."""
    checks = (
        (OrderItem, OrderItem.item_id), (VentaExterna, VentaExterna.item_id),
        (CartItem, CartItem.item_id), (PeticionCliente, PeticionCliente.item_id),
        (Assignacio, Assignacio.item_id), (SolicitudCompraLinea, SolicitudCompraLinea.item_resuelto_id),
        (DevolucionVenta, DevolucionVenta.item_id), (DevolucionCompra, DevolucionCompra.item_id),
        (StockHold, StockHold.item_id),
    )
    return any(
        db.scalar(select(func.count()).select_from(model).where(col == item_id))
        for model, col in checks
    )


def _consolidar_duplicados_nou(db, dry_run: bool, log=print) -> int:
    """Fusiona en una sola fila los releases que ya tienen más de una línea
    `nou` (herencia del modelo anterior, una fila por unidad). Ver docstring
    del módulo para el criterio exacto. Devuelve cuántos releases se han
    consolidado."""
    grupos = db.execute(
        select(Item.release_id, func.count(Item.id))
        .where(Item.condition == CondicionItem.nou)
        .group_by(Item.release_id)
        .having(func.count(Item.id) > 1)
    ).all()

    consolidados = 0
    for release_id, _ in grupos:
        items = list(db.scalars(
            select(Item).where(Item.release_id == release_id, Item.condition == CondicionItem.nou)
        ))
        if any(_tiene_dependientes(db, it.id) for it in items):
            release = db.get(Release, release_id)
            log(
                f"  [omitido] {release.artista} - {release.title}: alguna de las "
                f"{len(items)} líneas tiene referencias externas, revisar a mano."
            )
            continue

        items.sort(key=lambda it: it.entry_date or it.created_at)
        superviviente, *resto = items

        cantidad_total = sum(it.quantity for it in items)
        coste_base = superviviente.acquisition_cost
        cantidad_acumulada = superviviente.quantity
        for it in resto:
            if it.acquisition_cost is not None:
                coste_previo = coste_base if coste_base is not None else it.acquisition_cost
                coste_base = (
                    (cantidad_acumulada * coste_previo + it.quantity * it.acquisition_cost)
                    / (cantidad_acumulada + it.quantity)
                )
            cantidad_acumulada += it.quantity
            if superviviente.codi_discogs is None and it.codi_discogs is not None:
                # Primero se vacía aquí y se aplica el flush: si no, la UPDATE
                # del superviviente y el DELETE de `it` pueden ejecutarse en
                # un orden que deje un instante con dos filas con el mismo
                # codi_discogs, violando la UNIQUE.
                codi = it.codi_discogs
                it.codi_discogs = None
                db.flush()
                superviviente.codi_discogs = codi

        superviviente.quantity = cantidad_total
        superviviente.acquisition_cost = coste_base

        release = db.get(Release, release_id)
        log(
            f"  {release.artista} - {release.title}: {len(items)} líneas -> 1 "
            f"(cantidad={cantidad_total}, codi_discogs={superviviente.codi_discogs})"
        )
        for it in resto:
            db.delete(it)
        consolidados += 1

    if not dry_run and consolidados:
        db.commit()
    return consolidados


def _parse_posted(value: str | None) -> datetime | None:
    """Data en què el listing es va publicar al Marketplace de Discogs (ISO 8601).
    Per a stock que ja hi era abans d'aquesta app (no ve de cap Compra), és la
    millor aproximació disponible a la data d'entrada real al magatzem."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fetch_username(token: str | None) -> str:
    """El token identifica un únic compte; en traiem el username via /oauth/identity
    (mateix token, no cal cap variable d'entorn nova)."""
    discogs._throttle()
    with discogs._client(token) as c:
        r = c.get("/oauth/identity")
        r.raise_for_status()
        return r.json()["username"]


def _fetch_inventory(token: str | None, username: str, limit: int = 0, on_page=None) -> list[dict]:
    """Totes les listings 'For Sale' del compte venedor (paginat). Reintenta
    davant 429 (rate limit). `on_page(feta, total_pagines)` per informar del progrés."""
    listings: list[dict] = []
    page = 1
    while True:
        for attempt in range(4):
            discogs._throttle()
            with discogs._client(token) as c:
                r = c.get(
                    f"/users/{username}/inventory",
                    params={"status": "For Sale", "per_page": 100, "page": page},
                )
            if r.status_code == 429 and attempt < 3:
                time.sleep(65 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            break
        listings.extend(data.get("listings", []))
        if on_page:
            on_page(page, (data.get("pagination") or {}).get("pages", 1))
        if limit and len(listings) >= limit:
            return listings[:limit]
        pagination = data.get("pagination", {})
        if page >= pagination.get("pages", 1):
            break
        page += 1
    return listings


def _find_or_create_release(db, token: str | None, discogs_release_id: int, description: str) -> Release:
    release = db.scalar(
        select(Release).join(RecordProduct).where(RecordProduct.discogs_release_id == discogs_release_id)
    )
    if release:
        return release

    artista, titulo = None, description
    if " - " in description:
        artista, titulo = description.split(" - ", 1)
        artista, titulo = artista.strip(), titulo.strip()

    if artista:
        release = db.scalar(
            select(Release).join(RecordProduct).where(RecordProduct.artista.ilike(artista), Release.title.ilike(titulo))
        )
        if release:
            # Ja existia (alta manual anterior, p. ex.): el vinculem a Discogs.
            release.discogs_release_id = discogs_release_id
            return release

    # Release nou de veritat: consultem dades completes (sello, format, any...).
    # Reintenta en 429 (rate limit) en comptes de saltar-se el disc directament:
    # amb milers de listings és fàcil topar-hi encara respectant el throttle.
    data = None
    for attempt in range(4):
        try:
            data = discogs.get_release(token, discogs_release_id)
            break
        except Exception as exc:
            if "429" in str(exc) and attempt < 3:
                wait = 65 * (attempt + 1)
                print(f"  429 rate limit (release {discogs_release_id}) — esperant {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise
    data = data or {}
    release = Release(
        artista=data.get("artista") or artista or "Desconegut",
        title=data.get("titulo") or titulo,
        sello=data.get("sello"),
        referencia=data.get("referencia"),
        anio=data.get("anio"),
        genero=data.get("genero"),
        pais=data.get("pais"),
        estilos=data.get("estilos"),
        formato=data.get("formato"),
        tracklist=data.get("tracklist"),
        credits=data.get("credits"),
        ean=data.get("ean"),
        image_url=data.get("imagen_url"),
        discogs_release_id=discogs_release_id,
    )
    db.add(release)
    db.flush()
    return release


INFORME_COLUMNES = [
    "accio", "codi_discogs", "discogs_release_id", "artista", "titol", "condicio",
    "estat_disc", "preu_app", "preu_discogs", "item_id", "motiu", "preu_proposat",
]


def _fila(accio, *, codi=None, release_id=None, artista=None, titol=None, condicio=None,
          estat_disc=None, preu_app=None, preu_discogs=None, item_id=None, motiu=None, preu_proposat=None) -> dict:
    return {
        "accio": accio, "codi_discogs": codi, "discogs_release_id": release_id, "artista": artista,
        "titol": titol, "condicio": condicio, "estat_disc": estat_disc, "preu_app": preu_app,
        "preu_discogs": preu_discogs, "item_id": item_id, "motiu": motiu, "preu_proposat": preu_proposat,
    }


def _fila_item(accio, item, *, codi=None, preu_discogs=None, motiu=None) -> dict:
    """Fila de l'informe per a un ítem que ja existeix a la BD."""
    release = item.release
    return _fila(
        accio, codi=codi if codi is not None else item.codi_discogs,
        release_id=release.discogs_release_id, artista=release.artista, titol=release.title,
        condicio=item.condition.value, estat_disc=item.estado_disco, preu_app=item.price,
        preu_discogs=preu_discogs, item_id=item.id, motiu=motiu,
    )




def _noop(*_a, **_k) -> None:
    return None


def run_inventory_sync(
    db, tenant: Tenant, *, dry_run: bool, limit: int = 0, max_retire_pct: float = 20.0,
    force: bool = False, reobrir_adopcio: bool = False, log=print, progress=_noop, actor: str | None = None,
) -> InventorySyncResult:
    """Executa (o simula, amb `dry_run`) la sincronització. La sessió ha d'estar
    fixada al tenant (`scoped_to`). En dry-run tot es fa igualment i es
    desfà al final amb `rollback`. Llança `InventorySyncAbort` si una
    salvaguarda atura una execució real (en dry-run només avisa).

    `log(str)` rep els missatges; `progress(fase, feta, total)` el progrés."""
    avisos: list[str] = []

    def avis(missatge: str) -> None:
        avisos.append(missatge)
        log(f"AVÍS: {missatge}")

    token = resolve_discogs_token(get_tenant_secrets(tenant.id))
    if not token:
        raise InventorySyncAbort(f"El tenant '{tenant.slug}' no té cap token de Discogs configurat.")

    adopcio = adopcio_feta(db)
    if adopcio and not dry_run and not reobrir_adopcio:
        raise InventorySyncAbort(
            f"L'adopció inicial ja es va fer ({adopcio.get('fet_el', 'data desconeguda')}): a partir d'aquí "
            "l'app és la font de veritat i aquest mode (Discogs mana) no s'ha de relançar."
        )
    if adopcio and dry_run:
        avis(f"l'adopció inicial ja consta com a feta ({adopcio.get('fet_el')}).")

    progress("connexio", 0, 0)
    username = _fetch_username(token)
    log(f"Compte Discogs autenticat: {username}")

    progress("inventari", 0, 0)
    listings = _fetch_inventory(
        token, username, limit, on_page=lambda feta, total: progress("inventari", feta, total),
    )
    log(f"Listings 'For Sale' a Discogs: {len(listings)}")

    # Fre 1: un inventari buit gairebé segur vol dir "compte equivocat", no
    # "s'ha venut tot" — retiraria tot el catàleg.
    if not listings:
        missatge = (
            f"Discogs no retorna cap listing 'For Sale' per al compte '{username}'. Probablement el token "
            "és d'un altre compte; si fos bo, es retiraria tot el catàleg vinculat."
        )
        if not (dry_run or force):
            raise InventorySyncAbort(f"{missatge} S'avorta. Revisa el token.")
        avis(missatge)

    # Punto de restauración automático ANTES de tocar nada (una execució real modifica el catàleg en bloc):
    # si no es pot guardar, s'avorta. Es pot tornar enrere des de Configuració › Còpies de seguretat.
    copia_previa = None
    if not dry_run:
        log("Guardant una còpia del catàleg abans de modificar-lo...")
        copia_previa = create_snapshot(db, label="Abans de la càrrega inicial", trigger="pre_load", actor=actor).id
        db.commit()

    progress("consolidacio", 0, 0)
    log("Consolidant línies `nou` duplicades (herència d'abans del stock agregat)...")
    consolidados = _consolidar_duplicados_nou(db, dry_run, log=log)
    log(f"  {consolidados} releases consolidats.")

    codis_discogs = {int(l["id"]) for l in listings}

    # Items locals ja vinculats a un listing (per detectar els que ja no hi són).
    items_locals = {
        i.codi_discogs: i
        for i in db.scalars(
            select(Item).join(RecordStockDetail, RecordStockDetail.item_id == Item.id)
            .where(RecordStockDetail.codi_discogs.isnot(None))
        ).all()
    }

    # Fre 2: quantes retirades implicaria aquesta execució (es calcula abans
    # de tocar res, perquè l'execució real fa commits parcials dins del bucle).
    # Amb --limit no hi ha retirades (inventari truncat), així que no aplica.
    disponibles_vinculats = [i for i in items_locals.values() if i.status == ItemStatus.disponible]
    per_retirar = [c for c, i in items_locals.items() if i.status == ItemStatus.disponible and c not in codis_discogs]
    pct_retirar = 100 * len(per_retirar) / len(disponibles_vinculats) if disponibles_vinculats else 0.0
    if not limit and pct_retirar > max_retire_pct:
        missatge = (
            f"S'haurien de retirar {len(per_retirar)} de {len(disponibles_vinculats)} ítems disponibles "
            f"vinculats a Discogs ({pct_retirar:.0f} %, límit {max_retire_pct:g} %)."
        )
        if not (dry_run or force):
            raise InventorySyncAbort(f"{missatge} S'avorta. Revisa l'informe de la simulació.")
        avis(missatge)

    # Línies `nou` ja existents per release_id, per poder-hi sumar quan
    # trobem un listing "For Sale" del mateix release que encara no
    # rastrejàvem (recentment consolidades, o donades d'alta a mà/ERP).
    nou_por_release = {
        i.release_id: i
        for i in db.scalars(select(Item).where(Item.condition == CondicionItem.nou)).all()
    }

    filas: list[dict] = []
    creados = actualizados = sumados = errores = 0
    total_listings = len(listings)
    for i, listing in enumerate(listings, 1):
        codi = int(listing["id"])
        rel_info = listing.get("release") or {}
        descripcio = rel_info.get("description", "")
        artista_d, _, titol_d = descripcio.partition(" - ")
        if not titol_d:
            artista_d, titol_d = None, descripcio

        try:
            precio_raw = listing.get("price", {}).get("value")
            if precio_raw is None:
                errores += 1
                log(f"  listing {codi}: sense preu, es salta")
                filas.append(_fila(
                    "error", codi=codi, release_id=rel_info.get("id"), artista=artista_d, titol=titol_d,
                    motiu="sense preu a Discogs",
                ))
                continue
            precio = Decimal(str(precio_raw))

            item_existent = items_locals.get(codi)
            if item_existent:
                # Ja el tenim: mantenim condició tal com estava, però el preu
                # sí es manté sincronitzat amb el que digui Discogs ara mateix.
                preu_anterior = item_existent.price
                canviat_preu = item_existent.price != precio
                canviat_data = False
                if canviat_preu:
                    item_existent.price = precio
                # Stock anterior a aquesta app (mai va passar per una Compra):
                # aprofitem per omplir fecha_entrada amb el "posted" de Discogs
                # si encara no en teníem cap.
                if item_existent.entry_date is None:
                    posted = _parse_posted(listing.get("posted"))
                    if posted is not None:
                        item_existent.entry_date = posted
                        canviat_data = True
                if canviat_preu or canviat_data:
                    actualizados += 1
                    fila = _fila_item(
                        "actualitzar_preu" if canviat_preu else "actualitzar_data_entrada",
                        item_existent, codi=codi, preu_discogs=precio,
                        motiu="preu diferent a Discogs" + (" + data d'entrada buida" if canviat_preu and canviat_data else ""),
                    )
                    fila["preu_app"] = preu_anterior  # el preu abans de sobreescriure'l
                    filas.append(fila)
                continue

            release = _find_or_create_release(db, token, rel_info["id"], descripcio)

            estado_disco = clean(listing.get("condition"))
            condicion = derive_condicion(estado_disco)
            fila_base = dict(
                codi=codi, release_id=rel_info.get("id"), artista=release.artista, titol=release.title,
                condicio=condicion.value, estat_disc=estado_disco, preu_discogs=precio,
            )

            if condicion == CondicionItem.nou:
                agregado = nou_por_release.get(release.id)
                if agregado is not None:
                    preu_anterior = agregado.price
                    agregado.quantity += 1
                    if agregado.price != precio:
                        agregado.price = precio
                    if agregado.codi_discogs is None:
                        agregado.codi_discogs = codi
                        items_locals[codi] = agregado
                    sumados += 1
                    filas.append(_fila(
                        "sumar_nou", **fila_base, preu_app=preu_anterior, item_id=agregado.id,
                        motiu="listing sense item local: se suma 1 a la línia nou existent",
                    ))
                else:
                    nuevo = Item(
                        release_id=release.id,
                        codi_discogs=codi,
                        price=precio,
                        condition=condicion,
                        status=ItemStatus.disponible,
                        entry_date=_parse_posted(listing.get("posted")),
                    )
                    db.add(nuevo)
                    db.flush()
                    nou_por_release[release.id] = nuevo
                    items_locals[codi] = nuevo
                    creados += 1
                    filas.append(_fila(
                        "crear", **fila_base, item_id=nuevo.id, motiu="listing de Discogs sense item a l'app (nou)",
                    ))
            else:
                nuevo = Item(
                    release_id=release.id,
                    codi_discogs=codi,
                    price=precio,
                    condition=condicion,
                    estado_disco=estado_disco,
                    estado_funda=clean(listing.get("sleeve_condition")),
                    status=ItemStatus.disponible,
                    entry_date=_parse_posted(listing.get("posted")),
                )
                db.add(nuevo)
                creados += 1
                filas.append(_fila(
                    "crear", **fila_base, motiu="listing de Discogs sense item a l'app (segona mà)",
                ))

            if i % 25 == 0:
                log(f"  [{i}/{total_listings}] ...")
            if not dry_run and i % 50 == 0:
                db.commit()  # progrés parcial: no perdre-ho tot si el procés es talla
        except Exception as exc:
            errores += 1
            log(f"  listing {codi}: error ({exc}), es salta")
            filas.append(_fila(
                "error", codi=codi, release_id=rel_info.get("id"), artista=artista_d, titol=titol_d,
                motiu=str(exc)[:200],
            ))
        finally:
            if i % 10 == 0 or i == total_listings:
                progress("processar", i, total_listings)

    # Retirar: disponibles localment amb codi_discogs que ja NO és "For Sale".
    # Per a nou, no es retira la línia sencera (representaria perdre les
    # altres unitats que encara hi ha): es descompta 1 unitat i es buida
    # el codi_discogs (mai republica ell mateix).
    # Amb --limit l'inventari està truncat: no es retira res.
    retirados = 0
    progress("retirar", 0, 0)
    if limit:
        log("--limit: no es retira cap ítem (inventari truncat).")
    else:
        for codi, item in items_locals.items():
            if codi in codis_discogs or item.status != ItemStatus.disponible:
                continue
            if item.condition == CondicionItem.nou:
                filas.append(_fila_item(
                    "descomptar_nou", item, codi=codi, motiu="el listing ja no és 'For Sale' a Discogs: -1 unitat",
                ))
                item.quantity = max(0, item.quantity - 1)
                item.codi_discogs = None
            else:
                filas.append(_fila_item(
                    "retirar", item, codi=codi, motiu="el listing ja no és 'For Sale' a Discogs: es marca retirat",
                ))
                item.status = ItemStatus.retirado
                item.reserved_until = None
                item.reserved_by_cart_id = None
            retirados += 1

    summary = {
        "dry_run": dry_run, "compte_discogs": username, "listings": len(listings), "creats": creados,
        "sumats": sumados, "actualitzats": actualizados, "retirats": retirados, "errors": errores,
        "pct_retirar": round(pct_retirar, 1), "avisos": avisos, "limit": limit, "adopcio_marcada": False,
        "copia_previa": copia_previa,
    }

    if dry_run:
        db.rollback()
    else:
        db.commit()
        # Reflejo con estado de los vínculos item <-> listing (fase A del plan).
        summary["channel_listings"] = backfill_discogs_listings(db)
        db.commit()
        if limit:
            log("Adopció NO marcada com a feta: s'ha executat amb límit.")
        elif errores:
            log(
                f"Adopció NO marcada com a feta: hi ha {errores} errors. Revisa'ls (i l'informe) i torna a "
                "executar-ho (és idempotent) fins que acabi sense errors."
            )
        else:
            marcar_adopcio_feta(db, {
                "listings": len(listings), "creats": creados, "sumats": sumados,
                "actualitzats": actualizados, "retirats": retirados, "compte_discogs": username,
            })
            db.commit()
            summary["adopcio_marcada"] = True
            log("Adopció marcada com a feta: a partir d'ara l'app és la font de veritat.")

    progress("fet", total_listings, total_listings)
    return InventorySyncResult(rows=filas, summary=summary)


def escribir_informe(filas: list[dict], ruta: str) -> None:
    import csv

    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=INFORME_COLUMNES)
        w.writeheader()
        w.writerows(filas)

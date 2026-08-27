"""Reconciliació del catàleg amb l'export CSV del Google Sheet (inventari
actiu a Discogs). Usat pel script manual `scripts/sync_catalog_sheet.py` i
per la tasca nocturna `tasks/catalog_sync.py`.

El sheet real fa servir un CSV brut exportat de Discogs; els noms de
columna de la capçalera (CODI, ARTISTA, ... PREU/PRECIO, ESTAT DISCO...)
no coincideixen amb la posició real de les dades (comprovat contra la BD:
p.ex. la columna titulada "PREU/PRECIO" conté el discogs_release_id, i la
titulada "ESTAT DISCO" conté el preu real). Per això es llegeix per
POSICIÓ de columna, no pel nom de la capçalera:

    0 CODI (listing id, -> Item.codi_discogs)
    1 ARTISTA
    2 TITOL / TÍTULO
    3 SEGELL / SELLO
    4 REFERENCIA
    5 FORMAT
    6 discogs_release_id
    7 status Discogs ("For Sale"...)
    8 PREU real
    9 data de publicació
    11 estat disc (grading)
    12 estat funda (grading)

Comportament (només afegeix i retira, no toca preus/condicions dels que
ja coincideixen — és deliberat, veure conversa amb l'usuari):
  - CODI al sheet que no existeix a la BD -> es crea Item (i Release si cal).
  - Item a la BD amb status=disponible i CODI que ja NO és al sheet
    -> es marca com a `retirado` (venut a Discogs/mostrador o retirat).
  - Mai toca items en estat reservado/vendido/retirado.
"""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CondicionItem, Item, ItemStatus, RecordProduct, RecordStockDetail, Release


def clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def derive_condicion(estado_disco: str | None) -> CondicionItem:
    """Qui introdueix les dades al full marca deliberadament Mint/Near Mint
    per als exemplars nous (de proveïdor); la resta és segona mà. No és una
    equivalència exacta amb el règim fiscal REBU (estat físic ≠ procedència
    legal), però és la senyal acordada amb la botiga per a aquest import."""
    valor = (estado_disco or "").strip().lower()
    if valor.startswith("mint") or valor.startswith("near mint"):
        return CondicionItem.nou
    return CondicionItem.segona_ma


def parse_fecha(value: str | None) -> datetime | None:
    value = clean(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_sheet_csv(csv_text: str) -> dict[int, list[str]]:
    """Retorna {codi_discogs: fila} a partir del text del CSV exportat."""
    reader = csv.reader(io.StringIO(csv_text))
    next(reader, None)  # capçalera (no fiable, veure docstring del mòdul)
    return {int(row[0]): row for row in reader if row and row[0].strip().isdigit()}


def diff_catalog(db: Session, sheet_codis: dict[int, list[str]]) -> dict:
    """Compara el sheet amb la BD sense escriure res."""
    db_items = {
        i.codi_discogs: i
        for i in db.query(Item)
        .join(RecordStockDetail, RecordStockDetail.item_id == Item.id)
        .filter(RecordStockDetail.codi_discogs.isnot(None))
        .all()
    }
    a_afegir = [codi for codi in sheet_codis if codi not in db_items]
    a_retirar = [
        codi for codi, item in db_items.items()
        if codi not in sheet_codis and item.status == ItemStatus.disponible
    ]
    return {"db_items": db_items, "a_afegir": a_afegir, "a_retirar": a_retirar}


def apply_sync(db: Session, sheet_codis: dict[int, list[str]], diff: dict) -> dict:
    """Aplica el diff calculat per `diff_catalog`: afegeix i retira. Fa commit."""
    creados = errores = 0
    for codi in diff["a_afegir"]:
        row = sheet_codis[codi]
        try:
            artista = clean(row[1])
            titulo = clean(row[2])
            sello = clean(row[3])
            referencia = clean(row[4])
            formato = clean(row[5])
            discogs_release_id = int(row[6]) if row[6].strip().isdigit() else None
            precio = Decimal(row[8].replace(",", "."))
            fecha_entrada = parse_fecha(row[9]) if len(row) > 9 else None
            estado_disco = clean(row[11]) if len(row) > 11 else None
            estado_funda = clean(row[12]) if len(row) > 12 else None

            if not (artista and titulo):
                errores += 1
                continue

            release = None
            if discogs_release_id:
                release = db.scalar(
                    select(Release).join(RecordProduct).where(RecordProduct.discogs_release_id == discogs_release_id)
                )
            if release is None:
                release = db.scalar(
                    select(Release).join(RecordProduct)
                    .where(RecordProduct.artista.ilike(artista), Release.title.ilike(titulo))
                )
            if release is None:
                release = Release(
                    artista=artista,
                    title=titulo,
                    sello=sello,
                    referencia=referencia,
                    formato=formato,
                    discogs_release_id=discogs_release_id,
                )
                db.add(release)
                db.flush()

            db.add(
                Item(
                    release_id=release.id,
                    codi_discogs=codi,
                    price=precio,
                    condition=derive_condicion(estado_disco),
                    estado_disco=estado_disco,
                    estado_funda=estado_funda,
                    entry_date=fecha_entrada,
                    status=ItemStatus.disponible,
                )
            )
            creados += 1
        except (InvalidOperation, ValueError):
            errores += 1

    retirados = 0
    for codi in diff["a_retirar"]:
        diff["db_items"][codi].status = ItemStatus.retirado
        retirados += 1

    db.commit()
    return {"creados": creados, "retirados": retirados, "errores": errores}

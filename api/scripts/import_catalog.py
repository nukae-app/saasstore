"""Importación única del catálogo desde el CSV exportado del Google Sheet.

Uso (dentro del contenedor api, o con el venv local activado):

    # 1. Exporta el sheet: Archivo -> Descargar -> CSV
    # 2. Importación básica (sin llamar a Discogs):
    python -m scripts.import_catalog catalogo.csv

    # 3. Con enriquecimiento (carátula + release id de Discogs, ~1 seg/disco):
    python -m scripts.import_catalog catalogo.csv --enrich

Columnas esperadas (las del sheet actual):
    CODI, ARTISTA, TITOL / TÍTULO, SEGELL / SELLO, REFERENCIA, FORMAT,
    PREU/PRECIO, DATA/FECHA ENTRADA, ESTAT DISCO, ESTAT FUNDA

Idempotente: si un CODI ya existe en la base de datos, se salta la fila,
así que se puede relanzar sin duplicar nada.
"""

import argparse
import csv
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Item, Release
from app.services import discogs

COLS = {
    "codi": "CODI",
    "artista": "ARTISTA",
    "titulo": "TITOL / TÍTULO",
    "sello": "SEGELL / SELLO",
    "referencia": "REFERENCIA",
    "formato": "FORMAT",
    "precio": "PREU/PRECIO",
    "fecha": "DATA/FECHA ENTRADA",
    "estado_disco": "ESTAT DISCO",
    "estado_funda": "ESTAT FUNDA",
}


def clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def infer_formato_sheet(raw: str | None) -> str | None:
    """El sheet és, en origen, un export de Discogs (veure CLAUDE.md): la
    columna FORMAT sol portar els mateixos tokens barrejats que la cerca de
    Discogs ("Vinyl, LP, Album, Reissue"), que mai farien match amb
    PesFormat.formato si es desessin tal qual. Reutilitza el mateix mapeig
    que l'alta assistida (services/discogs.infer_formato)."""
    tokens = [t.strip() for t in (raw or "").split(",") if t.strip()]
    return discogs.infer_formato(tokens) or clean(raw)


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="ruta al CSV exportado del sheet")
    parser.add_argument("--enrich", action="store_true", help="consultar Discogs por cada CODI (lento)")
    parser.add_argument("--limit", type=int, default=0, help="procesar solo N filas (para probar)")
    args = parser.parse_args()

    db = SessionLocal()
    creados, saltados, errores = 0, 0, 0
    releases_cache: dict[tuple, Release] = {}

    with open(args.csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        # Trigger header read, then strip whitespace from column names
        _ = reader.fieldnames
        reader.fieldnames = [f.strip() for f in reader.fieldnames]
        for n, row in enumerate(reader, start=1):
            if args.limit and creados >= args.limit:
                break
            try:
                codi_raw = clean(row.get(COLS["codi"]))
                artista = clean(row.get(COLS["artista"]))
                titulo = clean(row.get(COLS["titulo"]))
                precio_raw = clean(row.get(COLS["precio"]))
                if not (artista and titulo and precio_raw):
                    continue  # fila vacía o cabecera repetida

                codi = int(codi_raw) if codi_raw and codi_raw.isdigit() else None
                if codi and db.scalar(select(Item).where(Item.codi_discogs == codi)):
                    saltados += 1
                    continue

                precio = Decimal(precio_raw.replace(",", "."))
                sello = clean(row.get(COLS["sello"]))
                referencia = clean(row.get(COLS["referencia"]))

                key = (artista.lower(), titulo.lower(), (referencia or "").lower())
                release = releases_cache.get(key)
                if release is None:
                    release = db.scalar(
                        select(Release).where(
                            Release.artista.ilike(artista),
                            Release.titulo.ilike(titulo),
                        )
                    )
                if release is None:
                    release = Release(
                        artista=artista,
                        titulo=titulo,
                        sello=sello,
                        referencia=referencia,
                        formato=infer_formato_sheet(row.get(COLS["formato"])),
                    )
                    db.add(release)
                    db.flush()
                releases_cache[key] = release

                if args.enrich and codi and release.discogs_release_id is None:
                    info = discogs.get_listing(codi)
                    if info:
                        release.discogs_release_id = info["discogs_release_id"]
                        if info.get("imagen_url") and not release.imagen_url:
                            release.imagen_url = info["imagen_url"]

                db.add(
                    Item(
                        release_id=release.id,
                        codi_discogs=codi,
                        precio=precio,
                        estado_disco=clean(row.get(COLS["estado_disco"])),
                        estado_funda=clean(row.get(COLS["estado_funda"])),
                        fecha_entrada=parse_fecha(row.get(COLS["fecha"])),
                    )
                )
                creados += 1
                if creados % 100 == 0:
                    db.commit()
                    print(f"  ... {creados} ejemplares importados")
            except (InvalidOperation, ValueError) as exc:
                errores += 1
                print(f"  fila {n}: error ({exc}), se salta", file=sys.stderr)

    db.commit()
    db.close()
    print(f"\nHecho: {creados} ejemplares creados, {saltados} ya existían, {errores} filas con error.")
    if not args.enrich:
        print("Consejo: relanza con --enrich para traer carátulas y release ids de Discogs.")


if __name__ == "__main__":
    main()

"""Importació de l'històric de compres des del CSV manual de control
("ULTRA-CONTROL"), per alimentar `historial_compres` (senyal de lectura
per al futur motor de recomanació de proveïdor).

Format esperat de columnes: DATA, DISCO, DISTRI, €, NOM, DOMICILI
(DATA en dd-mm-yyyy).

Ús:
    python -m scripts.import_historial_compres ruta.csv              # dry-run
    python -m scripts.import_historial_compres ruta.csv --commit      # escriu a BD

Es descarten files que no són compres reals a proveïdor:
  - DISTRI buit o dins la llista d'exclusió (BUSCAR, CREDIT, VALE, DIPOSIT, XXX, XXXX)
  - DISTRI que sembla una persona (conté un telèfon, 6+ dígits seguits)
  - Data invàlida o fora de rang raonable (2015-2027)

Per artista/títol: NOMÉS es parseja quan DISCO segueix el patró fiable
"Artista - Títol"; si no, es deixa en blanc (el text cru sempre queda a
`notas`, que és cercable). No s'endevina res via Discogs: un match no
confirmat és pitjor que cap match.

Quan artista+títol es parsegen amb confiança, es busca una coincidència
EXACTA (cas-insensitive) al catàleg propi (`releases`); si n'hi ha una de
sola, s'hi enllaça `release_id` (dona accés a EAN i segell reals, sense
crides externes).

Idempotent: no torna a inserir una línia si ja n'hi ha una amb el mateix
(proveedor_id, fecha, precio_coste, notas) — `notas` guarda el text original
de DISCO tal qual venia al CSV.
"""

import argparse
import csv
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import HistorialCompra, Proveedor, Release

EXCLUDED_DISTRI = {
    "BUSCAR", "BUSCO", "CREDIT", "VALE", "DIPOSIT", "XXX", "XXXX",
    "SEGONA MA BUSCAR", "SEGONA MÀ BUSCAR", "",
    # Noms de particulars (no distribuïdores) que el detector de telèfon/email
    # no atrapa perquè la fila concreta no en porta: verificat manualment
    # (contra el propi context del CSV — notes de dipòsit/crèdit, telèfon en
    # una altra fila del mateix venedor— i una cerca web sense resultats de
    # cap empresa amb aquest nom) que són compres a particulars, no a proveïdor.
    "ALB 625 2/5", "KEVIN12-19", "JULIA IVAN", "HELSINKI DIPOSIT", "CESC",
    "DANI EMPTY", "XAVI GARATGE", "MANUEL CALIFATO", "CARLITOS PAISA",
}
PHONE_RE = re.compile(r"\d{6,}")
EMAIL_RE = re.compile(r"@")
NOISE_SUFFIX_RE = re.compile(r"\s+(DISTRI|LIQUIDAT)$", re.IGNORECASE)
YEAR_MIN, YEAR_MAX = 2015, 2027


def fix_mojibake(value: str) -> str:
    """Muchas files del CSV original venen amb UTF-8 mal decodificat com
    Latin-1 (Ã© en lloc de é). Prova de revertir-ho; si no es pot, retorna
    el text original sense tocar."""
    try:
        return value.encode("latin1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return value


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return fix_mojibake(value).strip()


def parse_fecha(value: str) -> date | None:
    value = clean(value)
    try:
        d = datetime.strptime(value, "%d-%m-%Y").date()
    except ValueError:
        return None
    if not (YEAR_MIN <= d.year <= YEAR_MAX):
        return None
    return d


def parse_precio(value: str) -> Decimal | None:
    value = clean(value).replace(",", ".")
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def normalize_distri(value: str) -> str:
    value = clean(value).upper()
    value = NOISE_SUFFIX_RE.sub("", value).strip()
    return value


def is_particular(distri_raw: str) -> bool:
    return bool(PHONE_RE.search(distri_raw)) or bool(EMAIL_RE.search(distri_raw))


def display_name(distri_norm: str) -> str:
    return distri_norm.title()


TRAILING_PARENS_RE = re.compile(r"\s*\([^()]*\)\s*$")


def strip_trailing_format_info(titulo: str) -> str:
    """Treu blocs finals entre parèntesis tipus '(LP, Album, RE)' només per
    intentar el matching contra el catàleg; el `titulo` guardat no es toca."""
    prev = None
    cleaned = titulo
    while cleaned != prev:
        prev = cleaned
        cleaned = TRAILING_PARENS_RE.sub("", cleaned).strip()
    return cleaned


def parse_disco(disco_raw: str) -> tuple[str | None, str | None]:
    """Retorna (artista, titulo) només quan DISCO segueix el patró fiable
    'Artista - Títol'; si no, (None, None) — es deixa en blanc."""
    disco = clean(disco_raw)
    if " - " in disco:
        artista, titulo = disco.split(" - ", 1)
        return artista.strip(), titulo.strip()
    return None, None


def match_release(db, artista: str, titulo: str) -> Release | None:
    """Coincidència EXACTA (case-insensitive) contra el catàleg propi. Només
    retorna resultat si n'hi ha exactament una fila que hi coincideixi."""
    titulo_net = strip_trailing_format_info(titulo)
    matches = db.scalars(
        select(Release).where(
            func.lower(Release.artista) == artista.lower(),
            func.lower(Release.titulo) == titulo_net.lower(),
        )
    ).all()
    return matches[0] if len(matches) == 1 else None


def get_or_create_proveedor(db, cache: dict, distri_norm: str, commit: bool) -> Proveedor | None:
    if distri_norm in cache:
        return cache[distri_norm]
    prov = db.scalar(select(Proveedor).where(Proveedor.nombre == display_name(distri_norm)))
    if prov is None:
        prov = Proveedor(nombre=display_name(distri_norm), tipo="distribuidor")
        if commit:
            db.add(prov)
            db.flush()
    cache[distri_norm] = prov
    return prov


def already_imported(db, proveedor_id, fecha, precio, notas) -> bool:
    return db.scalar(
        select(HistorialCompra.id).where(
            HistorialCompra.proveedor_id == proveedor_id,
            HistorialCompra.fecha == fecha,
            HistorialCompra.precio_coste == precio,
            HistorialCompra.notas == notas,
        ).limit(1)
    ) is not None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--commit", action="store_true", help="Escriu de veritat a la BD (per defecte: dry-run)")
    parser.add_argument("--limit", type=int, default=None, help="Nombre màxim de files a processar (per proves)")
    args = parser.parse_args()

    db = SessionLocal()
    prov_cache: dict[str, Proveedor] = {}

    stats = {
        "total": 0, "excluidas_token": 0, "excluidas_particular": 0,
        "data_invalida": 0, "preu_invalid": 0, "importades": 0,
        "ja_existien": 0, "sense_parsejar": 0, "release_trobat": 0,
    }
    proveidors_count: dict[str, int] = {}

    with open(args.csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for n, row in enumerate(reader, start=2):
            if args.limit and stats["total"] >= args.limit:
                break
            stats["total"] += 1

            distri_raw = clean(row.get("DISTRI"))
            distri_norm = normalize_distri(distri_raw)

            if distri_norm in EXCLUDED_DISTRI:
                stats["excluidas_token"] += 1
                continue
            if is_particular(distri_raw):
                stats["excluidas_particular"] += 1
                continue

            fecha = parse_fecha(row.get("DATA", ""))
            if fecha is None:
                stats["data_invalida"] += 1
                print(f"  fila {n}: data invàlida '{row.get('DATA')}' -> descartada")
                continue

            precio = parse_precio(row.get("€", ""))
            if precio is None:
                stats["preu_invalid"] += 1
                print(f"  fila {n}: preu invàlid '{row.get('€')}' -> descartada")
                continue

            disco_raw = clean(row.get("DISCO"))
            artista, titulo = parse_disco(disco_raw)
            if artista is None:
                stats["sense_parsejar"] += 1

            proveidors_count[distri_norm] = proveidors_count.get(distri_norm, 0) + 1

            if not args.commit:
                if artista and titulo and match_release(db, artista, titulo):
                    stats["release_trobat"] += 1
                stats["importades"] += 1
                continue

            prov = get_or_create_proveedor(db, prov_cache, distri_norm, commit=True)
            if already_imported(db, prov.id, fecha, precio, disco_raw):
                stats["ja_existien"] += 1
                continue

            release = match_release(db, artista, titulo) if (artista and titulo) else None
            if release:
                stats["release_trobat"] += 1

            db.add(HistorialCompra(
                proveedor_id=prov.id, fecha=fecha, artista=artista, titulo=titulo,
                sello=release.sello if release else None,
                release_id=release.id if release else None,
                precio_coste=precio, notas=disco_raw,
            ))
            stats["importades"] += 1

        if args.commit:
            db.commit()

    print("\n--- Resum ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"\n  Proveïdors detectats ({len(proveidors_count)}):")
    for nom, count in sorted(proveidors_count.items(), key=lambda kv: -kv[1]):
        print(f"    {display_name(nom):30s} {count}")

    if not args.commit:
        print("\n(dry-run: no s'ha escrit res a la BD. Repeteix amb --commit per aplicar-ho.)")


if __name__ == "__main__":
    main()

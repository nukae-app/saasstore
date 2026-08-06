"""Sincronitza el catàleg amb l'export CSV del Google Sheet (inventari actiu a Discogs).

Veure app/services/catalog_sync.py per l'explicació del format del CSV i
el comportament (afegir/retirar, mai tocar preus/condicions ni items
reservats/venuts). Aquesta versió és per llançar-la a mà; la sincronització
automàtica nocturna és la tasca Celery `catalog.sync_discogs_sheet`.

Per defecte NOMÉS INFORMA (dry-run). Cal --apply per escriure canvis.

Ús:
    docker compose exec api python -m scripts.sync_catalog_sheet /tmp/catalog_sheet.csv
    docker compose exec api python -m scripts.sync_catalog_sheet /tmp/catalog_sheet.csv --apply
"""

import argparse

from app.database import SessionLocal
from app.services.catalog_sync import apply_sync, diff_catalog, parse_sheet_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", help="ruta al CSV exportat del sheet")
    parser.add_argument("--apply", action="store_true", help="escriu els canvis (per defecte només informa)")
    args = parser.parse_args()

    with open(args.csv_path, encoding="utf-8") as fh:
        sheet_codis = parse_sheet_csv(fh.read())

    db = SessionLocal()
    diff = diff_catalog(db, sheet_codis)

    print(f"Files al sheet: {len(sheet_codis)}")
    print(f"Items a la BD amb codi_discogs: {len(diff['db_items'])}")
    print(f"A AFEGIR (nous al sheet): {len(diff['a_afegir'])}")
    print(f"A RETIRAR (disponibles que ja no són al sheet): {len(diff['a_retirar'])}")

    if not args.apply:
        print("\nDry-run: no s'ha escrit res. Relança amb --apply per aplicar els canvis.")
        db.close()
        return

    result = apply_sync(db, sheet_codis, diff)
    db.close()
    print(f"\nFet: {result['creados']} items afegits, {result['retirados']} marcats com a retirado, {result['errores']} errors.")


if __name__ == "__main__":
    main()

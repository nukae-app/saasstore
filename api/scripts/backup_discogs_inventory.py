"""Còpia de seguretat (NOMÉS LECTURA) de l'inventari del Marketplace de Discogs.

Només fa GET a Discogs: no crea, edita ni elimina res, i no toca la BD ni
cap secret de l'app. Pensat per fer-se ABANS de la primera sincronització
"Discogs mana" (scripts/sync_discogs_inventory.py, docs/PLAN_CANAL_DISCOGS.md
§8), que sí modifica la BD.

El token es passa per entorn (DISCOGS_TOKEN), no per argument, perquè no quedi
a l'historial de la shell ni a la llista de processos. Pot ser el token del
compte venedor de la botiga encara que no estigui desat a l'app.

Genera, dins `--out-dir/discogs_<compte>_<data>/`:
  - inventory.json  respostes completes de Discogs (màxima fidelitat)
  - inventory.csv   vista plana per revisar/obrir en un full de càlcul
  - orders.json     només amb --orders (històric de comandes; pot tardar)
  - manifest.json   compte, data, recomptes per estat i estats que han fallat

Ús (des de api/):
  DISCOGS_TOKEN=... python -m scripts.backup_discogs_inventory
  DISCOGS_TOKEN=... python -m scripts.backup_discogs_inventory --orders --out-dir ~/backups/discogs
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

from app.services import discogs

# "For Sale" és l'imprescindible; la resta es proven de manera tolerant (si
# Discogs rebutja algun estat, es deixa constància al manifest i se segueix).
STATUSES = ["For Sale", "Draft", "Suspended", "Expired"]

CSV_COLUMNES = [
    "listing_id", "status", "release_id", "descripcio", "format", "cat_no", "preu", "moneda",
    "condicio", "condicio_funda", "comentaris", "external_id", "ubicacio", "posted", "permet_ofertes",
]


def _get(path: str, token: str, params: dict) -> dict:
    """GET amb throttle i reintent davant 429 (rate limit)."""
    for attempt in range(4):
        discogs._throttle()
        with discogs._client(token) as c:
            r = c.get(path, params=params)
        if r.status_code == 429 and attempt < 3:
            wait = 65 * (attempt + 1)
            print(f"  429 rate limit — esperant {wait}s...", flush=True)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("inabastable")  # pragma: no cover


def _get_paged(path: str, token: str, key: str, params: dict) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        data = _get(path, token, {**params, "per_page": 100, "page": page})
        items.extend(data.get(key, []))
        pages = (data.get("pagination") or {}).get("pages", 1)
        print(f"  {path} {params.get('status', '')} pàg. {page}/{pages} ({len(items)} fins ara)", flush=True)
        if page >= pages:
            return items
        page += 1


def _fila_csv(listing: dict) -> dict:
    rel = listing.get("release") or {}
    preu = listing.get("price") or {}
    return {
        "listing_id": listing.get("id"), "status": listing.get("status"), "release_id": rel.get("id"),
        "descripcio": rel.get("description"), "format": rel.get("format"), "cat_no": rel.get("catalog_number"),
        "preu": preu.get("value"), "moneda": preu.get("currency"), "condicio": listing.get("condition"),
        "condicio_funda": listing.get("sleeve_condition"), "comentaris": listing.get("comments"),
        "external_id": listing.get("external_id"), "ubicacio": listing.get("location"),
        "posted": listing.get("posted"), "permet_ofertes": listing.get("allow_offers"),
    }


def run(token: str, out_dir: Path, orders: bool = False) -> Path:
    username = discogs.get_identity(token)
    print(f"Compte Discogs autenticat: {username}", flush=True)

    destino = out_dir.expanduser() / f"discogs_{username}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    destino.mkdir(parents=True, exist_ok=False)

    listings: list[dict] = []
    per_estat: dict[str, int] = {}
    fallats: dict[str, str] = {}
    for estat in STATUSES:
        try:
            trobats = _get_paged(f"/users/{username}/inventory", token, "listings", {"status": estat})
        except httpx.HTTPError as exc:
            if estat == "For Sale":
                raise  # sense l'inventari a la venda, la còpia no val res
            fallats[estat] = str(exc)[:200]
            print(f"  AVÍS: no s'ha pogut llegir l'estat '{estat}': {exc}", file=sys.stderr, flush=True)
            continue
        per_estat[estat] = len(trobats)
        listings.extend(trobats)

    (destino / "inventory.json").write_text(json.dumps(listings, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(destino / "inventory.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNES)
        w.writeheader()
        w.writerows(_fila_csv(l) for l in listings)

    n_orders = None
    if orders:
        ordres = _get_paged("/marketplace/orders", token, "orders", {"sort": "created", "sort_order": "desc"})
        n_orders = len(ordres)
        (destino / "orders.json").write_text(json.dumps(ordres, ensure_ascii=False, indent=1), encoding="utf-8")

    manifest = {
        "compte": username, "creat_el": datetime.now().isoformat(timespec="seconds"),
        "listings_per_estat": per_estat, "listings_total": len(listings),
        "estats_fallats": fallats, "comandes": n_orders,
    }
    (destino / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nCòpia feta a {destino}: {per_estat} ({len(listings)} listings).", flush=True)
    if per_estat.get("For Sale", 0) == 0:
        print("AVÍS: 0 listings 'For Sale'. Comprova que el token és del compte venedor de la botiga.", file=sys.stderr)
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", default="backups/discogs", help="carpeta on crear la còpia (def. backups/discogs)")
    parser.add_argument("--orders", action="store_true", help="inclou també l'històric de comandes del Marketplace")
    args = parser.parse_args()

    token = os.environ.get("DISCOGS_TOKEN")
    if not token:
        raise SystemExit("Falta la variable d'entorn DISCOGS_TOKEN (token del compte venedor de la botiga).")
    run(token, Path(args.out_dir), orders=args.orders)


if __name__ == "__main__":
    main()

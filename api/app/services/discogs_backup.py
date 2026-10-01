"""Copia del inventario y los pedidos de Discogs (solo lectura de Discogs).

Núcleo compartido por el script `scripts/backup_discogs_inventory.py` (a mano, en ficheros) y por el botón
de la pantalla (trabajo en segundo plano; la copia se guarda en `channel_backups`, comprimida, y se
descarga como JSON o CSV). Solo hace GET a Discogs: no modifica nada."""

import csv
import gzip
import io
import json
import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from ..models import CHANNEL_DISCOGS, ChannelBackup, Tenant
from ..models.channels import BACKUP_DISCOGS
from . import discogs
from .discogs_inventory_sync import InventorySyncResult
from .discogs_sync import get_discogs_token_if_enabled

log = logging.getLogger(__name__)

# "For Sale" es el imprescindible; el resto se prueban de forma tolerante.
STATUSES = ["For Sale", "Draft", "Suspended", "Expired"]
CSV_COLUMNES = [
    "listing_id", "status", "release_id", "descripcio", "format", "cat_no", "preu", "moneda",
    "condicio", "condicio_funda", "comentaris", "external_id", "ubicacio", "posted", "permet_ofertes",
]


class BackupAbort(Exception):
    """No se puede hacer la copia (mensaje para el usuario)."""


def get_json(path: str, token: str, params: dict) -> dict:
    """GET con límite de llamadas y reintento ante 429 (rate limit)."""
    for attempt in range(4):
        discogs._throttle()
        with discogs._client(token) as c:
            r = c.get(path, params=params)
        if r.status_code == 429 and attempt < 3:
            time.sleep(65 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("inabastable")  # pragma: no cover


def get_paged(path: str, token: str, key: str, params: dict, on_page=None) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        data = get_json(path, token, {**params, "per_page": 100, "page": page})
        items.extend(data.get(key, []))
        pages = (data.get("pagination") or {}).get("pages", 1)
        if on_page:
            on_page(page, pages, len(items))
        if page >= pages:
            return items
        page += 1


def fila_csv(listing: dict) -> dict:
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


def fetch_everything(token: str, username: str, *, orders: bool, log_fn=print, progress=lambda *a, **k: None, paged=None):
    """Descarga el inventario (todos los estados) y, opcionalmente, los pedidos. Devuelve
    (listings, per_estat, fallats, ordres|None)."""
    paged = paged or get_paged
    listings: list[dict] = []
    per_estat: dict[str, int] = {}
    fallats: dict[str, str] = {}
    for estat in STATUSES:
        try:
            trobats = paged(
                f"/users/{username}/inventory", token, "listings", {"status": estat},
                on_page=lambda p, total, n, e=estat: (log_fn(f"  {e}: pàgina {p}/{total} ({n})"), progress("inventari", p, total)),
            )
        except httpx.HTTPError as exc:
            if estat == "For Sale":
                raise
            fallats[estat] = str(exc)[:200]
            log_fn(f"AVÍS: no s'ha pogut llegir l'estat '{estat}': {exc}")
            continue
        per_estat[estat] = len(trobats)
        listings.extend(trobats)
    ordres = None
    if orders:
        ordres = paged(
            "/marketplace/orders", token, "orders", {"sort": "created", "sort_order": "desc"},
            on_page=lambda p, total, n: (log_fn(f"  comandes: pàgina {p}/{total} ({n})"), progress("comandes", p, total)),
        )
    return listings, per_estat, fallats, ordres


def run_discogs_backup(
    db: Session, tenant: Tenant, *, orders: bool = True, actor: str | None = None, log_fn=print,
    progress=lambda *a, **k: None,
) -> InventorySyncResult:
    """Copia el inventario (y pedidos) de Discogs a `channel_backups`. Hace commit."""
    token = get_discogs_token_if_enabled(db, tenant.id)
    if token is None:
        raise BackupAbort("Discogs està desactivat o no hi ha cap token configurat.")
    try:
        username = discogs.get_identity(token)
    except httpx.HTTPError as exc:
        raise BackupAbort(f"No s'ha pogut verificar el compte de Discogs: {exc}") from exc
    log_fn(f"Compte Discogs autenticat: {username}")
    progress("connexio", 0, 0)

    listings, per_estat, fallats, ordres = fetch_everything(token, username, orders=orders, log_fn=log_fn, progress=progress)
    if per_estat.get("For Sale", 0) == 0:
        log_fn("AVÍS: 0 listings 'For Sale'. Comprova que el token és del compte venedor de la botiga.")

    raw = gzip.compress(json.dumps({
        "version": 1, "compte": username, "taken_at": datetime.now(timezone.utc).isoformat(),
        "inventory": listings, "orders": ordres,
    }, ensure_ascii=False, separators=(",", ":")).encode())
    summary = {
        "compte": username, "listings_per_estat": per_estat, "listings_total": len(listings),
        "comandes": None if ordres is None else len(ordres), "estats_fallats": fallats,
    }
    db.add(ChannelBackup(
        id=uuid.uuid4().hex, channel=CHANNEL_DISCOGS, kind=BACKUP_DISCOGS, trigger="manual",
        label=f"Inventari de Discogs ({username})", summary=summary, size_bytes=len(raw), payload=raw,
        created_by=actor or "sistema",
    ))
    db.commit()
    log_fn(f"Còpia feta: {per_estat} ({len(listings)} listings).")
    return InventorySyncResult(rows=[], summary={**summary, "mode": "discogs_backup", "errors": 0, "avisos": []})


def inventory_csv(payload: dict) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNES)
    w.writeheader()
    w.writerows(fila_csv(l) for l in payload.get("inventory", []))
    return buf.getvalue()

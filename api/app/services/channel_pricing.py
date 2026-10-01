"""Precios de mercado de Discogs (solo lectura) y reprecio a partir de ellos.

- Consulta por release: precios sugeridos por estado del disco, estadísticas del Marketplace
  (precio más bajo, nº a la venta) y comisión. Se cachean 6 h para no gastar las ~60 llamadas/min.
- Vista previa masiva (trabajo en segundo plano): propone un precio por item a partir de la sugerencia
  de Discogs para SU estado, con un factor y un redondeo. NO cambia nada.
- Aplicar: cambia el precio en LA APP (la fuente de verdad) de los items elegidos, solo si no han
  cambiado desde la vista previa. Después, la reconciliación propaga el precio a Discogs (Listings)."""

import json
import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Item, RecordProduct, Release, Tenant
from . import discogs, discogs_jobs
from .channel_events import record_event
from .channel_reconciler import sellable_clause
from .channel_settings import get_settings
from .discogs_inventory_sync import InventorySyncResult, _fila
from .discogs_sync import _map_condition, get_discogs_token_if_enabled

log = logging.getLogger(__name__)

CACHE_TTL = 6 * 3600
MAX_PREVIEW_ITEMS = 500
CODE_TO_KEY = {
    "M": "Mint (M)", "NM": "Near Mint (NM or M-)", "VG+": "Very Good Plus (VG+)", "VG": "Very Good (VG)",
    "G+": "Good Plus (G+)", "G": "Good (G)", "F": "Fair (F)", "P": "Poor (P)",
}
ACCIO_PUJA, ACCIO_BAIXA, ACCIO_IGUAL, ACCIO_SENSE = "repreu_puja", "repreu_baixa", "igual", "sense_suggeriment"


class PricingAbort(Exception):
    """Se para la consulta de precios (mensaje para el usuario)."""


def condition_key(item: Item) -> str:
    """Clave de la sugerencia de Discogs para el estado de este item (`nou` = Mint)."""
    return "Mint (M)" if item.condition.value == "nou" else CODE_TO_KEY[_map_condition(item.estado_disco)]


def round_to(value: Decimal, step: Decimal | float) -> Decimal:
    step = Decimal(str(step))
    if step <= 0:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return ((value / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step).quantize(Decimal("0.01"))


def propose(suggestion: Decimal, *, factor: float, step: float, recargo_pct) -> Decimal:
    """Precio de la APP que, tras el recargo del canal, deja el de Discogs en `suggestion * factor`."""
    base = Decimal(str(suggestion)) * Decimal(str(factor)) / (Decimal(1) + Decimal(str(recargo_pct)) / Decimal(100))
    return round_to(base, step)


def _cached(key: str, loader):
    kv = discogs_jobs._kv()
    try:
        raw = kv.get(key)
        if raw:
            return json.loads(raw)
    except Exception:  # noqa: BLE001 — la caché es una optimización
        log.warning("channel_pricing: caché no disponible", exc_info=True)
    value = loader()
    try:
        kv.set(key, json.dumps(value), ex=CACHE_TTL)
    except Exception:  # noqa: BLE001
        pass
    return value


def _explain(exc: httpx.HTTPStatusError) -> str:
    return f"Discogs {exc.response.status_code}: {exc.response.text[:200]}"


def _seller_settings_problem(exc: httpx.HTTPStatusError) -> bool:
    return exc.response.status_code in (401, 403) or "seller" in exc.response.text.lower()


def market_for_release(token: str, release_id: int, *, with_stats: bool = True) -> dict:
    """Sugerencias (+ estadísticas) de un release, con caché. Propaga `PricingAbort` si Discogs
    rechaza por los ajustes de vendedor; otros errores HTTP, como `httpx.HTTPStatusError`."""
    try:
        suggestions = _cached(f"discogs:sug:{release_id}", lambda: discogs.get_price_suggestions(token, release_id))
    except httpx.HTTPStatusError as exc:
        if _seller_settings_problem(exc):
            raise PricingAbort(
                "Discogs no deixa consultar els preus suggerits: completa els ajustes de venedor al teu compte "
                f"de Discogs ({_explain(exc)})."
            ) from exc
        raise
    out = {"release_id": release_id, "suggestions": suggestions, "stats": None}
    if with_stats:
        out["stats"] = _cached(f"discogs:stats:{release_id}", lambda: discogs.get_release_stats(token, release_id))
    return out


def fee_for(token: str, price: float) -> dict:
    return _cached(f"discogs:fee:{round(float(price), 2)}", lambda: discogs.get_fee(token, price))


def run_pricing_preview(
    db: Session, tenant: Tenant, *, item_ids: set | None = None, limit: int = 200, factor: float = 1.0,
    step: float = 0.5, min_diff_pct: float = 5.0, log_fn=print, progress=lambda *a, **k: None,
) -> InventorySyncResult:
    token = get_discogs_token_if_enabled(db, tenant.id)
    if token is None:
        raise PricingAbort("Discogs està desactivat o no hi ha cap token configurat.")
    recargo = get_settings(db).recargo_pct
    limit = max(1, min(int(limit), MAX_PREVIEW_ITEMS))

    stmt = (
        select(Item, RecordProduct.discogs_release_id, Release.title, RecordProduct.artista)
        .join(Release, Release.id == Item.release_id)
        .join(RecordProduct, RecordProduct.release_id == Release.id)
        .where(sellable_clause(), RecordProduct.discogs_release_id.isnot(None))
        .order_by(RecordProduct.artista, Release.title)
    )
    if item_ids:
        stmt = stmt.where(Item.id.in_(item_ids))
    candidatos = db.execute(stmt.limit(limit)).all()
    log_fn(f"Consultant preus de Discogs per a {len(candidatos)} items…")

    filas: list[dict] = []
    contadores = {ACCIO_PUJA: 0, ACCIO_BAIXA: 0, ACCIO_IGUAL: 0, ACCIO_SENSE: 0, "error": 0}
    progress("preus", 0, len(candidatos))
    for i, (item, rid, titol, artista) in enumerate(candidatos, 1):
        base = dict(
            release_id=rid, artista=artista, titol=titol, condicio=item.condition.value, estat_disc=item.estado_disco,
            preu_app=item.price, item_id=item.id, codi=item.codi_discogs,
        )
        key = condition_key(item)
        try:
            market = market_for_release(token, rid, with_stats=False)
            sug = (market["suggestions"] or {}).get(key)
            if not sug:
                accio, motiu, proposat, raw = ACCIO_SENSE, f"Discogs no té suggeriment per a «{key}»", None, None
            elif sug.get("currency") not in (None, "EUR"):
                accio, motiu, proposat, raw = "error", f"moneda del suggeriment {sug.get('currency')} ≠ EUR", None, sug.get("value")
            else:
                raw = Decimal(str(sug["value"]))
                proposat = propose(raw, factor=factor, step=step, recargo_pct=recargo)
                diff = (proposat - item.price) / item.price * 100 if item.price else Decimal(0)
                if abs(diff) < Decimal(str(min_diff_pct)) or proposat <= 0:
                    accio = ACCIO_IGUAL
                else:
                    accio = ACCIO_PUJA if diff > 0 else ACCIO_BAIXA
                motiu = f"{diff:+.0f} % · {key}"
            contadores["error" if accio == "error" else accio] += 1
            filas.append(_fila(accio, **base, preu_discogs=raw, preu_proposat=proposat, motiu=motiu))
        except PricingAbort:
            raise
        except Exception as exc:  # noqa: BLE001 — un release problemático no debe parar el resto
            contadores["error"] += 1
            filas.append(_fila("error", **base, motiu=str(exc)[:200]))
        if i % 5 == 0 or i == len(candidatos):
            progress("preus", i, len(candidatos))

    summary = {
        "mode": "pricing_preview", "total": len(candidatos), "puja": contadores[ACCIO_PUJA],
        "baixa": contadores[ACCIO_BAIXA], "igual": contadores[ACCIO_IGUAL], "sense_suggeriment": contadores[ACCIO_SENSE],
        "errors": contadores["error"], "factor": factor, "step": step, "min_diff_pct": min_diff_pct,
        "avisos": [], "dry_run": True,
    }
    log_fn(f"Fet: {summary['puja']} pugen, {summary['baixa']} baixen, {summary['igual']} igual, "
           f"{summary['sense_suggeriment']} sense suggeriment, {summary['errors']} errors.")
    return InventorySyncResult(rows=filas, summary=summary)


def apply_prices(db: Session, rows: list[dict], selected: set[str] | None, actor: str | None) -> dict:
    """Cambia en la app el precio de los items elegidos de una vista previa. Salta los que ya no están
    a la venta o cuyo precio cambió desde la vista previa (no se pisa una edición posterior). Sin commit."""
    from .channel_reconciler import is_sellable

    aplicats, saltats = 0, []
    for r in rows:
        if r["accio"] not in (ACCIO_PUJA, ACCIO_BAIXA) or not r.get("preu_proposat"):
            continue
        if selected is not None and r["item_id"] not in selected:
            continue
        item = db.get(Item, uuid.UUID(str(r["item_id"])))
        if item is None or not is_sellable(item):
            saltats.append({"item_id": r["item_id"], "motiu": "ja no està a la venda"})
            continue
        anterior, nuevo = Decimal(str(r["preu_app"])), Decimal(str(r["preu_proposat"]))
        if item.price != anterior:
            saltats.append({"item_id": r["item_id"], "motiu": "el preu ha canviat des de la simulació"})
            continue
        item.price = nuevo
        record_event(db, "price_change", "ok", item_id=item.id, actor=actor,
                     detail={"from": float(anterior), "to": float(nuevo), "source": "discogs_suggestion"})
        aplicats += 1
    db.flush()
    return {"aplicats": aplicats, "saltats": saltats}

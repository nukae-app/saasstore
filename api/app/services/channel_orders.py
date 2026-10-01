"""Sondeo de pedidos del canal Discogs (entrada de ventas hechas allí).

Incremental: guarda un cursor (`channel_settings.orders_cursor`) con la actividad más reciente ya
procesada y solo recorre lo posterior (la primera vez, los últimos 60 días), en lugar de bajar
todo el histórico en cada ejecución. Los pedidos entran en `orders` con origen `discogs`, igual que
siempre, y se ven en "Vendes web". Las incidencias (sin coincidencia, conflicto, estado desconocido)
quedan en el registro de actividad. No hay webhooks de pedidos confirmados: se consulta cada 5–10 min."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..models import Tenant
from .channel_alerts import raise_alert, resolve_alerts
from .channel_events import record_event
from .channel_notifications import notify_new_orders, send_pending
from .channel_settings import get_settings
from .discogs_sync import (
    _parse_iso, fetch_open_discogs_orders, get_discogs_token_if_enabled, sync_discogs_orders,
)

log = logging.getLogger(__name__)


class OrdersPullError(Exception):
    """No se ha podido sondear (sin token, Discogs caído...). El mensaje es para el usuario."""


def _max_activity(orders: list[dict]) -> datetime | None:
    fechas = [d for d in (_parse_iso(o.get("last_activity")) for o in orders) if d is not None]
    return max(fechas) if fechas else None


def pull_orders(db: Session, tenant: Tenant, *, full: bool = False, now: datetime | None = None) -> dict:
    """Sondea los pedidos y los procesa. `full=True` ignora el cursor (últimos 60 días).
    Guarda el resultado en los ajustes del canal y hace commit. Propaga `OrdersPullError`."""
    now = now or datetime.now(timezone.utc)
    token = get_discogs_token_if_enabled(db, tenant.id)
    if token is None:
        raise OrdersPullError("Discogs està desactivat o no hi ha cap token configurat.")
    settings = get_settings(db)
    since = None if full else settings.orders_cursor
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    try:
        orders = fetch_open_discogs_orders(token, since=since, raise_errors=True)
    except Exception as exc:  # noqa: BLE001
        settings.orders_last_pull_at = now
        settings.orders_last_result = {"error": str(exc)[:300], "at": now.isoformat(timespec="seconds")}
        record_event(db, "order_pull", "error", detail={"kind": "fetch"}, error=str(exc))
        raise_alert(
            db, "orders_poll_failed", "orders_poll", f"No s'han pogut consultar les comandes de Discogs: {exc}",
            severity="error", detail={"error": str(exc)[:300]},
        )
        db.commit()
        _avisar(db)
        raise OrdersPullError(f"No s'han pogut consultar les comandes de Discogs: {exc}") from exc

    summary = sync_discogs_orders(db, token, orders)

    settings = get_settings(db)  # la sesión pudo hacer commit/rollback durante el proceso
    # El cursor solo avanza si todo se procesó: un fallo se reintenta (el proceso es idempotente).
    if not summary["errors"]:
        settings.orders_cursor = _max_activity(orders) or since or (now - timedelta(minutes=15))
    settings.orders_last_pull_at = now
    resultado = {**summary, "orders_fetched": len(orders), "at": now.isoformat(timespec="seconds"), "completa": full}
    settings.orders_last_result = resultado
    if summary["creats"] or summary["actualitzats"] or summary["errors"]:
        record_event(db, "order_pull", "ok" if not summary["errors"] else "error", detail={
            k: resultado[k] for k in ("creats", "actualitzats", "sense_match", "conflictes", "errors", "orders_fetched")
        })
    resolve_alerts(db, kind="orders_poll_failed")  # el sondeo vuelve a funcionar
    db.commit()
    _avisar(db, summary.get("nous") or [])
    return resultado


def _avisar(db: Session, nuevos_pedidos: list[dict] | None = None) -> None:
    """Correos de lo ocurrido (alertas nuevas y pedidos nuevos); jamás rompe el sondeo."""
    try:
        send_pending(db)
        notify_new_orders(db, nuevos_pedidos or [])
    except Exception:  # noqa: BLE001
        log.warning("channel_orders: no se pudieron enviar los avisos", exc_info=True)


def is_due(settings, now: datetime | None = None) -> bool:
    """¿Toca sondear ya, según la frecuencia configurada?"""
    now = now or datetime.now(timezone.utc)
    last = settings.orders_last_pull_at
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= timedelta(minutes=settings.orders_poll_minutes)

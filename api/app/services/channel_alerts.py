"""Bandeja de alertas del canal (`channel_alerts`): excepciones accionables, deduplicadas.

`raise_alert` es idempotente por `ref_key`: la misma incidencia detectada otra vez no crea otra
fila (una alerta resuelta que reaparece se reabre; una DESCARTADA no vuelve a abrirse sola). Las
alertas nuevas o reabiertas se encolan en la sesión para avisar por correo al final de la
operación (`channel_notifications.send_pending`), de una vez y no una por alerta. No hace commit."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import CHANNEL_DISCOGS, ChannelAlert
from ..models.channels import ALERT_DISMISSED, ALERT_OPEN, ALERT_RESOLVED

PENDING_KEY = "channel_pending_alerts"

# Tipo de alerta -> evento de aviso (lo que el usuario activa o no en sus preferencias)
EVENT_FOR_KIND = {
    "order_sense_match": "order_issue", "order_conflict": "order_issue",
    "order_status_unknown": "order_issue", "orders_poll_failed": "order_issue",
    "listing_error": "listing_error", "listing_gone": "listing_error",
    "sync_failed": "sync_failed", "retire_guard": "sync_failed",
    "audit_orphan_listing": "audit_discrepancies", "audit_missing_listing": "audit_discrepancies",
    "audit_price_diff": "audit_discrepancies", "audit_summary": "audit_discrepancies",
}


def raise_alert(
    db: Session, kind: str, ref_key: str, message: str, *, severity: str = "warning", item_id=None, order_id=None,
    external_id=None, detail: dict | None = None, channel: str = CHANNEL_DISCOGS, notify: bool = True,
) -> ChannelAlert:
    alert = db.scalar(select(ChannelAlert).where(ChannelAlert.channel == channel, ChannelAlert.ref_key == ref_key))
    nueva = False
    if alert is None:
        alert = ChannelAlert(
            channel=channel, kind=kind, severity=severity, ref_key=ref_key, message=message, detail=detail,
            item_id=item_id, order_id=order_id, external_id=str(external_id) if external_id is not None else None,
        )
        db.add(alert)
        nueva = True
    elif alert.status == ALERT_RESOLVED:
        alert.status = ALERT_OPEN
        alert.resolved_at = None
        alert.occurrences += 1
        alert.message, alert.detail, alert.severity = message, detail, severity
        nueva = True
    elif alert.status == ALERT_OPEN:
        alert.message, alert.detail = message, detail
    # ALERT_DISMISSED: el usuario ya dijo que no le interesa; se deja como está.
    db.flush()
    if nueva and notify:
        db.info.setdefault(PENDING_KEY, []).append(alert)
    return alert


def resolve_alerts(
    db: Session, *, kind: str | None = None, ref_key: str | None = None, keep_ref_keys: set[str] | None = None,
    channel: str = CHANNEL_DISCOGS,
) -> int:
    """Resuelve las alertas abiertas que coincidan. Con `keep_ref_keys`, resuelve las de ese `kind`
    cuyo `ref_key` ya NO está en el conjunto (la condición desapareció)."""
    stmt = select(ChannelAlert).where(ChannelAlert.channel == channel, ChannelAlert.status == ALERT_OPEN)
    if kind:
        stmt = stmt.where(ChannelAlert.kind == kind)
    if ref_key:
        stmt = stmt.where(ChannelAlert.ref_key == ref_key)
    n = 0
    for alert in db.scalars(stmt).all():
        if keep_ref_keys is not None and alert.ref_key in keep_ref_keys:
            continue
        alert.status = ALERT_RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)
        n += 1
    db.flush()
    return n


def set_status(db: Session, alert_id, status: str) -> ChannelAlert | None:
    """Resuelve o descarta a mano (`resolved` | `dismissed`) o reabre (`open`)."""
    alert = db.get(ChannelAlert, alert_id)
    if alert is None:
        return None
    alert.status = status
    alert.resolved_at = datetime.now(timezone.utc) if status in (ALERT_RESOLVED, ALERT_DISMISSED) else None
    db.flush()
    return alert


def list_alerts(
    db: Session, *, status: str | None = ALERT_OPEN, kind: str | None = None, limit: int = 50, offset: int = 0,
) -> tuple[int, list[ChannelAlert]]:
    stmt = select(ChannelAlert)
    count = select(func.count()).select_from(ChannelAlert)
    for col, value in ((ChannelAlert.status, status), (ChannelAlert.kind, kind)):
        if value:
            stmt, count = stmt.where(col == value), count.where(col == value)
    rows = db.scalars(stmt.order_by(ChannelAlert.created_at.desc()).limit(limit).offset(offset)).all()
    return db.scalar(count), list(rows)


def open_counts(db: Session) -> dict[str, int]:
    """Alertas abiertas por severidad (para el resumen)."""
    rows = db.execute(
        select(ChannelAlert.severity, func.count()).where(ChannelAlert.status == ALERT_OPEN).group_by(ChannelAlert.severity)
    ).all()
    return {sev: n for sev, n in rows}

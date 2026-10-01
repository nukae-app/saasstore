"""Avisos por correo del canal, configurables por cada usuario admin (por defecto, ninguno).

Eventos disponibles (`EVENTS`): lo que el usuario activa en Configuració. Las alertas nuevas se
agrupan por evento y se mandan en UN correo por usuario y evento al terminar la operación (un
barrido con 200 discrepancias no son 200 correos). Fallar al enviar nunca rompe la operación."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import NotificationPref, Tenant, User
from .channel_alerts import EVENT_FOR_KIND, PENDING_KEY
from .emailer import send_email

log = logging.getLogger(__name__)

EVENTS = [
    {"key": "new_order", "label": "Nova comanda de Discogs"},
    {"key": "order_issue", "label": "Incidència amb una comanda (sense coincidència, conflicte o estat desconegut) o error en consultar-les"},
    {"key": "listing_error", "label": "Error en publicar o actualitzar un listing"},
    {"key": "sync_failed", "label": "Sincronització fallida o aturada per seguretat"},
    {"key": "audit_discrepancies", "label": "Discrepàncies amb Discogs detectades a l'auditoria"},
]
EVENT_KEYS = {e["key"] for e in EVENTS}
_SUBJECT = {
    "new_order": "Discogs: {n} comanda(es) nova(es)",
    "order_issue": "Discogs: {n} incidència(es) amb comandes",
    "listing_error": "Discogs: {n} error(s) de listing",
    "sync_failed": "Discogs: sincronització fallida",
    "audit_discrepancies": "Discogs: {n} discrepància(es) detectada(es)",
}


def get_prefs(db: Session, user_id) -> dict[str, bool]:
    """Preferencias del usuario (todas las del catálogo; sin fila = desactivado)."""
    activas = {
        p.event_key: p.email for p in db.scalars(select(NotificationPref).where(NotificationPref.user_id == user_id))
    }
    return {e["key"]: bool(activas.get(e["key"], False)) for e in EVENTS}


def set_prefs(db: Session, user_id, values: dict[str, bool]) -> dict[str, bool]:
    for key, enabled in values.items():
        if key not in EVENT_KEYS:
            continue
        pref = db.scalar(select(NotificationPref).where(NotificationPref.user_id == user_id, NotificationPref.event_key == key))
        if pref is None:
            db.add(NotificationPref(user_id=user_id, event_key=key, email=bool(enabled)))
        else:
            pref.email = bool(enabled)
    db.flush()
    return get_prefs(db, user_id)


def _recipients(db: Session, event_key: str) -> list[User]:
    ids = db.scalars(
        select(NotificationPref.user_id).where(NotificationPref.event_key == event_key, NotificationPref.email.is_(True))
    ).all()
    if not ids:
        return []
    return list(db.scalars(select(User).where(User.id.in_(ids), User.role == "admin", User.active.is_(True))))


def _send(db: Session, event_key: str, lines: list[str]) -> int:
    destinatarios = _recipients(db, event_key)
    if not destinatarios or not lines:
        return 0
    tenant = db.get(Tenant, db.info["tenant_id"])
    asunto = _SUBJECT[event_key].format(n=len(lines))
    cuerpo = "\n".join(f"- {l}" for l in lines[:30])
    if len(lines) > 30:
        cuerpo += f"\n… i {len(lines) - 30} més."
    cuerpo += "\n\nConsulta el detall al centre de control de Discogs (Catàleg › Sync Discogs)."
    enviados = 0
    for user in destinatarios:
        try:
            send_email(user.email, asunto, cuerpo, tenant, db)
            enviados += 1
        except Exception:  # noqa: BLE001
            log.warning("channel_notifications: no se pudo avisar a %s", user.email, exc_info=True)
    return enviados


def send_pending(db: Session) -> int:
    """Envía los avisos de las alertas nuevas/reabiertas encoladas en la sesión (y vacía la cola)."""
    pendientes = db.info.pop(PENDING_KEY, [])
    por_evento: dict[str, list[str]] = {}
    for alert in pendientes:
        evento = EVENT_FOR_KIND.get(alert.kind)
        if evento:
            por_evento.setdefault(evento, []).append(alert.message)
    return sum(_send(db, evento, lines) for evento, lines in por_evento.items())


def notify_new_orders(db: Session, pedidos: list[dict]) -> int:
    """Aviso de pedidos de Discogs recién llegados (uno solo, aunque lleguen varios a la vez)."""
    if not pedidos:
        return 0
    lines = [f"Comanda {p['id']} de {p.get('buyer') or 'un comprador'}: {p.get('total')} €" for p in pedidos]
    return _send(db, "new_order", lines)

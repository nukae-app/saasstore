"""Registro de actividad de los canales de venta (`channel_events`).

Todo lo que se intenta escribir en un canal (publicar, retirar, marcar
enviado...) deja una fila con el resultado, también cuando no se escribe
(`skipped`, p. ej. por el modo solo lectura). Alimenta la auditoría y, más
adelante, la bandeja de Alertes. No hace commit: la fila viaja en la
transacción de quien la llama."""

import logging
import uuid

from sqlalchemy.orm import Session

from ..models import CHANNEL_DISCOGS, ChannelEvent

log = logging.getLogger(__name__)
SISTEMA = "sistema"


def record_event(
    db: Session | None, action: str, outcome: str, *, channel: str = CHANNEL_DISCOGS,
    item_id: uuid.UUID | None = None, order_id: uuid.UUID | None = None, external_id=None,
    actor: str | None = None, detail: dict | None = None, error: str | None = None,
) -> None:
    """Añade el evento a la sesión (sin commit). Nunca debe romper la operación
    que se está registrando: ante cualquier fallo solo deja una traza."""
    if db is None:
        return
    try:
        db.add(ChannelEvent(
            channel=channel, action=action, outcome=outcome, item_id=item_id, order_id=order_id,
            external_id=str(external_id) if external_id is not None else None,
            actor=actor or SISTEMA, detail=detail, error=(error[:2000] if error else None),
        ))
    except Exception:  # noqa: BLE001
        log.warning("channel_events: no se pudo registrar %s/%s", action, outcome, exc_info=True)

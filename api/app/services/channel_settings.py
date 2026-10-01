"""Ajustes del canal (`channel_settings`): una fila por tenant y canal, creada con
los valores por defecto la primera vez que se lee."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CHANNEL_DISCOGS, ChannelSettings

EDITABLE = {"publicacion_auto", "sync_auto", "recargo_pct", "orders_auto", "orders_poll_minutes"}


def get_settings(db: Session, channel: str = CHANNEL_DISCOGS) -> ChannelSettings:
    """Fila de ajustes del tenant de la sesión (la crea si no existe; hace flush, no commit)."""
    row = db.scalar(select(ChannelSettings).where(ChannelSettings.channel == channel))
    if row is None:
        row = ChannelSettings(channel=channel)
        db.add(row)
        db.flush()
    return row


def auto_publish_allowed(db: Session, channel: str = CHANNEL_DISCOGS) -> bool:
    """¿Se pueden publicar listings automáticamente (al dar de alta o reponer tras una venta)?
    Por defecto NO: se publica desde la pestaña Listings, con vista previa (decisión del plan)."""
    return bool(get_settings(db, channel).publicacion_auto)


def update_settings(db: Session, values: dict, channel: str = CHANNEL_DISCOGS) -> ChannelSettings:
    """Aplica solo campos editables ya validados (sin commit)."""
    row = get_settings(db, channel)
    for key, value in values.items():
        if key in EDITABLE and value is not None:
            setattr(row, key, Decimal(str(value)) if key == "recargo_pct" else value)
    db.flush()
    return row


def serialize(row: ChannelSettings) -> dict:
    return {
        "publicacion_auto": row.publicacion_auto, "sync_auto": row.sync_auto,
        "recargo_pct": float(row.recargo_pct), "orders_auto": row.orders_auto,
        "orders_poll_minutes": row.orders_poll_minutes, "orders_last_pull_at": row.orders_last_pull_at,
        "orders_last_result": row.orders_last_result,
    }

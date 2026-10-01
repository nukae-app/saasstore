"""Canales de venta online (Discogs hoy; Amazon u otros a futuro). Tablas
genéricas de canal — ver docs/PLAN_CANAL_DISCOGS.md §5 (fase A).

- `ChannelListing`: el vínculo item ↔ publicación en un canal, con estado,
  último precio publicado y último error (antes solo existía
  `record_stock_details.codi_discogs`, sin estado).
- `ChannelEvent`: registro de actividad (todo lo que se escribe en un canal).
- `ChannelSyncRun`: historial persistente de sincronizaciones (el estado en
  vivo de un trabajo sigue en Redis, ver services/discogs_jobs.py).

`status`/`outcome`/`kind` son cadenas libres (constantes aquí), no Enums de
BD: añadir un canal o un estado no debe obligar a migrar tipos."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Mapped, Session, deferred, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid

CHANNEL_DISCOGS = "discogs"

LISTING_PENDENT = "pendent"
LISTING_PUBLICAT = "publicat"
LISTING_ERROR = "error"
LISTING_RETIRAT = "retirat"

EVENT_OK = "ok"
EVENT_ERROR = "error"
EVENT_SKIPPED = "skipped"  # p. ej. modo solo lectura: se intentó pero no se escribió

RUN_QUEUED = "queued"
RUN_RUNNING = "running"
RUN_DONE = "done"
RUN_ERROR = "error"


class ChannelListing(TenantScoped, Base):
    __tablename__ = "channel_listings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "channel", "item_id"),
        UniqueConstraint("tenant_id", "channel", "external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    item: Mapped["Item"] = relationship("Item")  # noqa: F821 — definido en models/stock.py
    channel: Mapped[str] = mapped_column(String(30), default=CHANNEL_DISCOGS, server_default=CHANNEL_DISCOGS)
    # id de la publicación en el canal (Discogs: listing id). Cadena para ser genérico.
    external_id: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default=LISTING_PENDENT, server_default=LISTING_PENDENT, index=True)
    published_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    published_condition: Mapped[str | None] = mapped_column(String(60))
    published_sleeve: Mapped[str | None] = mapped_column(String(60))
    desired_hash: Mapped[str | None] = mapped_column(String(64))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChannelEvent(TenantScoped, Base):
    __tablename__ = "channel_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    channel: Mapped[str] = mapped_column(String(30), default=CHANNEL_DISCOGS, server_default=CHANNEL_DISCOGS, index=True)
    # publish | update | remove | ship | order_pull | sync_run ...
    action: Mapped[str] = mapped_column(String(40), index=True)
    outcome: Mapped[str] = mapped_column(String(20), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(60))
    actor: Mapped[str | None] = mapped_column(String(120))  # email del usuario o "sistema"
    detail: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ChannelSyncRun(TenantScoped, Base):
    __tablename__ = "channel_sync_runs"

    # Mismo id que el trabajo de Redis (services/discogs_jobs.py): uuid4().hex.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    channel: Mapped[str] = mapped_column(String(30), default=CHANNEL_DISCOGS, server_default=CHANNEL_DISCOGS, index=True)
    kind: Mapped[str] = mapped_column(String(30))  # inventory_dry_run | inventory_apply
    status: Mapped[str] = mapped_column(String(20), default=RUN_QUEUED, server_default=RUN_QUEUED)
    options: Mapped[dict | None] = mapped_column(JSON)
    summary: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    error_kind: Mapped[str | None] = mapped_column(String(20))
    rows_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Informe por item (hasta miles de filas): no se carga salvo que se pida.
    report: Mapped[list | None] = deferred(mapped_column(JSON))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChannelSettings(TenantScoped, Base):
    """Ajustes por tenant y canal (una fila; se crea con los valores por defecto la
    primera vez que se piden). El modo solo lectura NO está aquí: es el interruptor
    `discogs_solo_lectura` de Configuració (TenantFeature)."""

    __tablename__ = "channel_settings"
    __table_args__ = (UniqueConstraint("tenant_id", "channel"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    channel: Mapped[str] = mapped_column(String(30), default=CHANNEL_DISCOGS, server_default=CHANNEL_DISCOGS)
    # Publicar listings nuevos (y reponer los de `nou` tras una venta) sin revisión previa.
    # Por defecto apagado: se publica desde la pestaña Listings, con vista previa.
    publicacion_auto: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Retirar listings cuando el item deja de estar a la venta, de forma programada.
    sync_auto: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Recargo (%) sobre el precio de la app al publicar. 0 = mismo precio que la web.
    recargo_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), server_default="0")
    # Sondeo programado de pedidos del canal.
    orders_auto: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    orders_poll_minutes: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    orders_cursor: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    orders_last_pull_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    orders_last_result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


ALERT_OPEN = "open"
ALERT_RESOLVED = "resolved"
ALERT_DISMISSED = "dismissed"  # el usuario la descarta: no vuelve a abrirse sola


class ChannelAlert(TenantScoped, Base):
    """Excepción accionable del canal (bandeja "Alertes"): un pedido sin coincidencia, un listing que
    no se puede publicar, una discrepancia con Discogs... Una fila por `ref_key` (deduplica: la misma
    incidencia detectada otra vez no crea otra alerta)."""

    __tablename__ = "channel_alerts"
    __table_args__ = (UniqueConstraint("tenant_id", "channel", "ref_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    channel: Mapped[str] = mapped_column(String(30), default=CHANNEL_DISCOGS, server_default=CHANNEL_DISCOGS)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(10), default="warning", server_default="warning")  # info|warning|error
    ref_key: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSON)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(12), default=ALERT_OPEN, server_default=ALERT_OPEN, index=True)
    occurrences: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPref(TenantScoped, Base):
    """Qué avisos quiere recibir cada usuario admin (por defecto ninguno)."""

    __tablename__ = "notification_prefs"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "event_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_key: Mapped[str] = mapped_column(String(40))
    email: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


# ---------------------------------------------------------------------------------------------
# Reflejo automático codi_discogs -> channel_listings
# ---------------------------------------------------------------------------------------------
# `record_stock_details.codi_discogs` sigue siendo la columna que usa el resto de la app (alta,
# botón manual, reposición de `nou`, importaciones...). Si esos flujos asignan o borran el código
# sin dejar rastro en `channel_listings`, el plan de reconciliación vería el item "sin listing" y
# propondría publicarlo OTRA VEZ (listing duplicado en Discogs). Este hook, a nivel de flush, lo
# evita para TODOS los caminos presentes y futuros: cada cambio de `codi_discogs` actualiza el
# vínculo en la misma transacción.

def _free_external_id(session: Session, codi: str, owner) -> None:
    """Si OTRO vínculo del canal retiene este código (p. ej. al consolidar líneas, el `codi_discogs` pasa
    de un item a otro), se lo quita: el nuevo dueño lo hereda. El UPDATE sale antes que el INSERT del
    nuevo dentro del mismo flush, así que no choca con la restricción de unicidad."""
    with session.no_autoflush:
        otros = session.scalars(
            select(ChannelListing).where(ChannelListing.channel == CHANNEL_DISCOGS, ChannelListing.external_id == codi)
        ).all()
    for otro in otros:
        if otro is not owner:
            otro.external_id = None
            if otro.status == LISTING_PUBLICAT:
                otro.status = LISTING_RETIRAT


@event.listens_for(Session, "before_flush")
def _mirror_codi_discogs(session: Session, flush_context, instances) -> None:
    from .stock import RecordStockDetail

    ahora = datetime.now(timezone.utc)
    pendientes: dict = {}
    for o in session.new:
        if isinstance(o, ChannelListing):
            pendientes[id(o.item) if o.item is not None else o.item_id] = o
    for obj in list(session.new) + list(session.dirty):
        if not isinstance(obj, RecordStockDetail) or obj.item is None:
            continue
        if obj not in session.new and not inspect(obj).attrs.codi_discogs.history.has_changes():
            continue
        item, codi = obj.item, obj.codi_discogs
        listing = pendientes.get(id(item)) or (pendientes.get(item.id) if item.id is not None else None)
        if listing is None and inspect(item).persistent:
            with session.no_autoflush:
                listing = session.scalar(
                    select(ChannelListing).where(ChannelListing.item_id == item.id, ChannelListing.channel == CHANNEL_DISCOGS)
                )
        if codi is not None:
            _free_external_id(session, str(codi), listing)
            if listing is None:
                nuevo = ChannelListing(
                    item=item, channel=CHANNEL_DISCOGS, external_id=str(codi), status=LISTING_PUBLICAT,
                    published_price=item.price, last_synced_at=ahora,
                    tenant_id=obj.tenant_id or session.info.get("tenant_id"),
                )
                session.add(nuevo)
                pendientes[id(item)] = nuevo
            elif listing.external_id != str(codi) or listing.status != LISTING_PUBLICAT:
                listing.external_id, listing.status = str(codi), LISTING_PUBLICAT
                listing.last_error, listing.last_synced_at = None, ahora
        elif listing is not None and listing.status == LISTING_PUBLICAT:
            listing.status, listing.last_synced_at = LISTING_RETIRAT, ahora

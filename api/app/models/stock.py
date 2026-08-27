import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid
from .catalog import Release


class ItemStatus(str, enum.Enum):
    disponible = "disponible"
    reservado = "reservado"
    vendido = "vendido"
    retirado = "retirado"  # p. ej. vendido en tienda física o en Discogs


class CondicionItem(str, enum.Enum):
    nou = "nou"
    segona_ma = "segona_ma"


class Item(TenantScoped, Base):
    """Para `segona_ma`: una copia física concreta, cada fila se vende como
    mucho una vez (ver `status`/`reserved_*` más abajo).

    Para `nou`: una línea de stock agregado — `cantidad` son las unidades
    físicas que hay en esta línea (todas idénticas: mismo precio, sin
    grading), y `status`/`reserved_*` NO se usan para regular la venta
    (solo `retirado` tiene sentido, para descatalogar la línea a mano).
    Las reservas y ventas parciales de una línea `nou` se gestionan con
    `cantidad_reservada` y la tabla `StockHold` (ver services/reservations.py),
    porque a diferencia de una copia única, una línea agregada puede tener
    varias reservas simultáneas de orígenes distintos (varios carritos, una
    petición de cliente, una asignación de club...)."""

    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_items_cantidad_no_negativa"),
        CheckConstraint(
            "reserved_quantity >= 0 AND reserved_quantity <= quantity",
            name="ck_items_cantidad_reservada_valida",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    release_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("releases.id", ondelete="RESTRICT"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    condition: Mapped[CondicionItem] = mapped_column(
        Enum(CondicionItem, name="condicion_item"), default=CondicionItem.segona_ma, index=True
    )
    # Unidades físicas en esta línea. Para segona_ma siempre 1 (una copia = una
    # fila, como siempre); para nou puede ser N (ver docstring de la clase).
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # Unidades de `quantity` retenidas por reservas activas (StockHold). Solo
    # relevante para nou: segona_ma sigue usando status='reservado'/'vendido'.
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, name="item_status"), default=ItemStatus.disponible, index=True
    )
    reserved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reserved_by_cart_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("carts.id", ondelete="SET NULL"))
    # Reserva llarga (72h) per a una PeticionCliente que recull i paga a botiga
    # (sense passarel·la, per tant sense Order). Comparteix `reserved_until` i
    # el mateix alliberament mandrós que el carret; mai els dos FK alhora.
    reserved_for_peticion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "peticiones_cliente.id", ondelete="SET NULL",
            use_alter=True, name="fk_items_reserved_for_peticion_id",
        )
    )
    # Reserva mentre l'admin revisa una proposta d'assignació de subscripció
    # (veure services/subscripcions.py): mateix patró que reserved_for_peticion_id,
    # sense caducitat perquè el ritme el marca l'admin, no un client esperant.
    reserved_for_assignacio_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "subscripcio_assignacions.id", ondelete="SET NULL",
            use_alter=True, name="fk_items_reserved_for_assignacio_id",
        )
    )
    entry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # L'admin marca a mà quins exemplars concrets són elegibles per al club
    # del disc (veure routers/admin_subscripcions.py, pantalla "Catàleg"): és
    # la safata d'on tria l'algorisme d'assignació, mai tot el catàleg
    # disponible directament.
    subscription_pool: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True
    )

    acquisition_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    compra_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("compras.id", ondelete="SET NULL"), index=True
    )
    rebu: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    release: Mapped[Release] = relationship(back_populates="items")
    compra: Mapped["Compra | None"] = relationship(back_populates="items")
    record_detail: Mapped["RecordStockDetail | None"] = relationship(
        back_populates="item", uselist=False, cascade="all, delete-orphan"
    )

    # Passthrough (lectura y escritura) a la extensión `RecordStockDetail` —
    # mismo patrón que Release.artista/etc. más arriba: el resto del código
    # que hacía `Item(codi_discogs=..., estado_disco=..., ...)` o
    # `item.estado_disco = ...` sigue funcionando; lo que cambia son los usos
    # a nivel de clase en queries (`Item.codi_discogs == ...`), que hay que
    # rehacer como join contra RecordStockDetail.
    def _ensure_record_detail(self) -> "RecordStockDetail":
        if self.record_detail is None:
            self.record_detail = RecordStockDetail()
        return self.record_detail

    @property
    def codi_discogs(self) -> int | None:
        return self.record_detail.codi_discogs if self.record_detail else None

    @codi_discogs.setter
    def codi_discogs(self, value: int | None) -> None:
        self._ensure_record_detail().codi_discogs = value

    @property
    def estado_disco(self) -> str | None:
        return self.record_detail.estado_disco if self.record_detail else None

    @estado_disco.setter
    def estado_disco(self, value: str | None) -> None:
        self._ensure_record_detail().estado_disco = value

    @property
    def estado_funda(self) -> str | None:
        return self.record_detail.estado_funda if self.record_detail else None

    @estado_funda.setter
    def estado_funda(self, value: str | None) -> None:
        self._ensure_record_detail().estado_funda = value


class RecordStockDetail(TenantScoped, Base):
    """Extensión 1:1 de Item con los campos propios del vertical "records"
    a nivel de copia física: grading (`estado_disco`/`estado_funda`) y el
    listing id de Discogs (`codi_discogs`). Pareja de `RecordProduct` a
    nivel de Item en vez de Release — ver docs/ARQUITECTURA_CORE_VERTICAL.md
    §4.2."""

    __tablename__ = "record_stock_details"
    __table_args__ = (UniqueConstraint("tenant_id", "codi_discogs"),)

    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    codi_discogs: Mapped[int | None] = mapped_column(BigInteger)  # listing id (columna CODI del Excel)
    estado_disco: Mapped[str | None] = mapped_column(String(60))  # grading Discogs: "Near Mint (NM or M-)"...
    estado_funda: Mapped[str | None] = mapped_column(String(60))

    item: Mapped["Item"] = relationship(back_populates="record_detail")


# ---------------------------------------------------------------------------
# Usuarios y autenticación (sin contraseñas)
# ---------------------------------------------------------------------------


class StockHold(TenantScoped, Base):
    """Retención de N unidades de una línea `Item` con stock agregado (nou).

    Para segona_ma, cada copia es su propia fila y la reserva vive en la
    propia fila (`Item.status`/`reserved_by_cart_id`/`reserved_for_peticion_id`/
    `reserved_for_assignacio_id`/`reserved_until`) porque solo puede haber un
    titular a la vez. Una línea `nou` puede tener varias retenciones
    simultáneas de orígenes distintos (dos carritos pujando por las últimas
    unidades, una petición de cliente, una asignación de club...), así que
    hace falta una tabla en vez de columnas únicas en `Item`.

    Exactamente uno de `cart_id` / `peticion_id` / `assignacio_id` / `order_id`
    debe estar relleno (se valida a nivel de aplicación, no de esquema):
    - `cart_id`: reserva normal de carrito (caduca a los ~20 min, igual que
      las reservas de segona_ma, ver services/reservations.py).
    - `peticion_id`: reserva larga (72h) de una PeticionCliente que recoge y
      paga en tienda, equivalente a `Item.reserved_for_peticion_id`.
    - `assignacio_id`: retención mientras el admin revisa una propuesta de
      asignación del club del disco, equivalente a
      `Item.reserved_for_assignacio_id` (sin caducidad, `reserved_until=None`).
    - `order_id`: pedido con `metodo_pago='tienda'` ya confirmado pero
      pendiente de recoger y pagar (72h), equivalente a la extensión de
      `reserved_until` que hoy se hace sobre el Item en checkout.py.
    """

    __tablename__ = "stock_holds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)

    cart_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    peticion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("peticiones_cliente.id", ondelete="CASCADE"), index=True
    )
    assignacio_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subscripcio_assignacions.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)

    # None = sin caducidad automática (p.ej. retención de club hasta que el
    # admin decide). Con caducidad, se libera de forma perezosa igual que las
    # reservas de segona_ma (ver services/reservations.py::release_expired).
    reserved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["Item"] = relationship()

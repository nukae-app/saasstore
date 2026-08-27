import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid
from .stock import CondicionItem
from .stock import Item


class Cart(TenantScoped, Base):
    """Carrito persistente: de un usuario logueado o de una sesión anónima."""

    __tablename__ = "carts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    session_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # cookie anónima
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(TenantScoped, Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "item_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    cart_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    # Para segona_ma siempre 1 (una copia física). Para nou, cantidad deseada
    # de esa línea de stock agregado.
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cart: Mapped[Cart] = relationship(back_populates="items")
    item: Mapped[Item] = relationship()


class OrderStatus(str, enum.Enum):
    pendiente_pago = "pendiente_pago"
    pagado = "pagado"
    enviado = "enviado"
    entregado = "entregado"
    cancelado = "cancelado"


class OrderOrigen(str, enum.Enum):
    """De dónde viene el pedido: checkout propio o venta detectada al Marketplace de Discogs.
    Comparten el mismo modelo (Order/OrderItem) y la misma pantalla de admin (Vendes web)."""

    web = "web"
    discogs = "discogs"
    subscripcio = "subscripcio"


class Order(TenantScoped, Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    # SET NULL: una cuenta se puede anonimizar/borrar (RGPD) sin destruir el pedido
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    contact_email: Mapped[str] = mapped_column(String(320))
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), default=OrderStatus.pendiente_pago, index=True
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Snapshot del cost d'enviament calculat a /checkout/confirm (veure
    # services/enviament.py); ja inclòs a `total`. 0 si recogida_tienda.
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), server_default="0")
    shipping_method: Mapped[str] = mapped_column(String(40))  # "envio" | "recogida_tienda"
    # "redsys" (pago online) | "tienda" (paga al recoger; solo con recogida_tienda,
    # útil también para hacer pruebas de checkout sin pasarela real)
    payment_method: Mapped[str] = mapped_column(String(20), default="redsys", server_default="redsys")
    shipping_address: Mapped[dict | None] = mapped_column(JSON)  # snapshot; null si recogida en tienda
    notes: Mapped[str | None] = mapped_column(Text)
    # Snapshot del idioma en que se hizo el checkout: para invitados (user_id
    # nulo) es la única señal de idioma disponible para el email de
    # confirmación y no se puede resolver más tarde (el webhook de Redsys que
    # confirma el pago no tiene contexto de request/sesión).
    language: Mapped[str] = mapped_column(String(5), default="ca", server_default="ca")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Etiqueta/enviament: de moment sempre a mà (número de seguiment i
    # transportista introduïts per l'admin); no hi ha integració amb cap API
    # de missatgeria.
    tracking_number: Mapped[str | None] = mapped_column(String(100))
    carrier: Mapped[str | None] = mapped_column(String(100))
    # Recollida a botiga: quan s'avisa el client per email que ja pot venir a
    # buscar la comanda (veure POST /admin/orders/{id}/avisar-recollida). Null
    # mentre encara no se li ha avisat.
    pickup_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Venda detectada al Marketplace de Discogs (origin='discogs'): mateix model, mateixa pantalla.
    origin: Mapped[OrderOrigen] = mapped_column(
        Enum(OrderOrigen, name="order_origen"), default=OrderOrigen.web, server_default="web", index=True
    )
    discogs_order_id: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    discogs_buyer: Mapped[str | None] = mapped_column(String(120))

    # Carrito que reservó los ejemplares (ver services/reservations.py). Se
    # guarda para poder llamar a confirm_sale desde la notificación de pago
    # (server-to-server, sin cookie de carrito) una vez Redsys autoriza el cobro.
    cart_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("carts.id", ondelete="SET NULL"))

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    payments: Mapped[list["Payment"]] = relationship(back_populates="order", order_by="Payment.created_at")


class PaymentStatus(str, enum.Enum):
    creado = "creado"
    autorizado = "autorizado"
    denegado = "denegado"
    error = "error"


class Payment(TenantScoped, Base):
    """Intento de cobro con una pasarela externa (Redsys). Un pedido puede
    tener varios intentos (p. ej. si el primero es denegado y se reintenta);
    el pedido solo pasa a `pagado` cuando UN intento llega a `autorizado`,
    vía la notificación server-to-server (ver routers/payments.py)."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20), default="redsys")
    # Ds_Merchant_Order: código que identifica el intento ante Redsys (4-12
    # caracteres, los 4 primeros numéricos). No es el id del Order.
    ds_order: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.creado, index=True
    )
    ds_response_code: Mapped[str | None] = mapped_column(String(10))
    ds_authorisation_code: Mapped[str | None] = mapped_column(String(20))
    raw_notification: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    order: Mapped["Order"] = relationship(back_populates="payments")


class OrderItem(TenantScoped, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        # Una copia de segunda mano solo puede venderse una vez — igual que
        # antes, pero ahora como índice único PARCIAL: una línea `nou` (stock
        # agregado) puede aparecer en varios OrderItem a lo largo del tiempo,
        # o con cantidad>1 en una misma línea. `condicion` es un snapshot (ver
        # más abajo), así que este índice no depende del estado actual de Item.
        Index(
            "ix_order_items_item_id_unico_segona_ma", "item_id",
            unique=True,
            postgresql_where=text("condition = 'segona_ma'"),
            sqlite_where=text("condition = 'segona_ma'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    # Nullable: línia "de reserva" d'una petició de client pagada per
    # endavant (Via 1) que encara no té exemplar físic assignat — en aquest
    # cas `release_id` diu quin disc s'ha de lliurar; quan arriba l'exemplar
    # real, s'omple `item_id` i es buida `release_id` (veure erp.py,
    # resolució de peticions).
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    release_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("releases.id", ondelete="RESTRICT"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # snapshot del precio al comprar
    # Snapshot de la condición al vender (igual criterio que `price`): para
    # nou puede haber varias OrderItem sobre la misma línea de Item a lo
    # largo del tiempo, así que hace falta guardar aquí qué condición tenía
    # en el momento de la venta, no leerla de `item.condition` (que además
    # puede quedar en None si `item_id` es una línea de reserva sin asignar).
    condition: Mapped[CondicionItem | None] = mapped_column(Enum(CondicionItem, name="condicion_item"))
    # Unidades vendidas en esta línea. Para segona_ma siempre 1; para nou
    # puede ser N (varias unidades de la misma línea en un mismo pedido).
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    # Snapshot del tipus d'IVA aplicat en el moment de la venda (nou vs segona mà/REBU).
    # Per a línies de reserva (item_id=None) es queda a None fins que
    # s'assigna l'exemplar real: l'IVA (REBU o no) depèn de la seva condició.
    tipus_iva_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipus_iva.id", ondelete="SET NULL"), index=True
    )
    vat_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    vat_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    order: Mapped[Order] = relationship(back_populates="items")
    item: Mapped["Item | None"] = relationship()
    release: Mapped["Release | None"] = relationship()
    tipus_iva: Mapped["TipusIva | None"] = relationship()


# ---------------------------------------------------------------------------
# ERP — entradas de stock (compras) y ventas externas
# ---------------------------------------------------------------------------

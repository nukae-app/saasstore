import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid


class Proveedor(TenantScoped, Base):
    """Proveedor unificat: discos i serveis generals (llum, gestor, transport...)."""

    __tablename__ = "proveedores"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    # Fase 4 Etapa B: atributo Python en inglés, ya alineado con el nombre
    # de columna que fijó la Etapa A.
    name: Mapped[str] = mapped_column(String(300), index=True)
    # type: distribuidor | proveidor_online | subministrador | professional | transport | particular | altres
    type: Mapped[str | None] = mapped_column(String(60))
    nif: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(String(500))
    contact: Mapped[str | None] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    supplier_iban: Mapped[str | None] = mapped_column(String(34))
    # transferencia | rebut_domiciliat | targeta | efectiu | paypal_altres
    payment_method: Mapped[str | None] = mapped_column(String(30))
    payment_days: Mapped[int | None] = mapped_column(Integer)     # 0, 30, 60, 90...
    payment_day_of_month: Mapped[int | None] = mapped_column(Integer)  # dia fix del mes (1-31)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    compras: Mapped[list["Compra"]] = relationship(back_populates="proveedor")
    despeses: Mapped[list["Despesa"]] = relationship(back_populates="proveidor", foreign_keys="Despesa.proveidor_id")
    historial_compres: Mapped[list["HistorialCompra"]] = relationship(back_populates="proveedor")


class TipoCompra(str, enum.Enum):
    proveedor = "proveedor"
    particular = "particular"


class Compra(TenantScoped, Base):
    """Lote de entrada de stock: compra a proveedor o a un particular en mostrador."""

    __tablename__ = "compras"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    # La columna de BD encara es diu "tipo" (es va quedar fora del batch de
    # renom de columnes de la Fase 4 Etapa A); l'atribut Python ja és en
    # anglès, d'aquí l'override explícit del nom de columna.
    type: Mapped[TipoCompra] = mapped_column(
        "tipo", Enum(TipoCompra, name="tipo_compra"), index=True
    )
    proveedor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    individual_name: Mapped[str | None] = mapped_column(String(300))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Referència de l'albarà/nota d'entrega (no és la factura: la factura es
    # registra a part i pot agrupar diverses recepcions, vegeu Despesa).
    delivery_note_number: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    # Coste total de ESTA recepción, fijado al crearla. Antes del stock
    # agregado bastaba con sumar `Item.acquisition_cost` de `Compra.items`
    # (cada Item pertenecía a una sola Compra); ahora una línea `nou` puede
    # acumular varias recepciones en la MISMA fila `Item` (que solo puede
    # apuntar a una `compra_id`, la última), así que ese cálculo derivado ya
    # no basta para saber cuánto costó cada recepción concreta — por eso se
    # guarda aquí explícitamente (usado por comptabilitat.py al facturar).
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    comanda_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comandas.id", ondelete="SET NULL"), index=True
    )

    # Diverses recepcions (Compra) es poden facturar juntes amb una única Despesa.
    despesa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("despeses.id", ondelete="SET NULL"), index=True
    )

    proveedor: Mapped["Proveedor | None"] = relationship(back_populates="compras")
    client: Mapped["User | None"] = relationship(back_populates="compres_client", foreign_keys=[user_id])
    items: Mapped[list["Item"]] = relationship(back_populates="compra")
    despesa: Mapped["Despesa | None"] = relationship(back_populates="compras")
    comanda: Mapped["Comanda | None"] = relationship(back_populates="compras")


class EstadoComanda(str, enum.Enum):
    esborrany = "esborrany"
    enviada = "enviada"
    rebuda_parcial = "rebuda_parcial"
    rebuda = "rebuda"
    cancelada = "cancelada"


class Comanda(TenantScoped, Base):
    """Comanda a proveïdor: es genera abans que arribi la mercaderia. La
    recepció (total o parcial) crea una Compra -> Items reals (pujada a stock),
    enllaçada aquí per traçabilitat."""

    __tablename__ = "comandas"
    __table_args__ = (UniqueConstraint("tenant_id", "order_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[EstadoComanda] = mapped_column(
        Enum(EstadoComanda, name="estado_comanda"), default=EstadoComanda.esborrany, index=True
    )
    order_number: Mapped[str] = mapped_column(String(20), index=True)  # "2026-000001"
    notes: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proveedor: Mapped["Proveedor"] = relationship()
    lineas: Mapped[list["ComandaLinea"]] = relationship(
        back_populates="comanda", cascade="all, delete-orphan", order_by="ComandaLinea.created_at"
    )
    compras: Mapped[list["Compra"]] = relationship(back_populates="comanda")


class ComandaLinea(TenantScoped, Base):
    """Línia d'una comanda: disc + quantitat demanada. cantidad_rebuda es va
    incrementant a cada recepció (pot ser parcial, en diverses tongades)."""

    __tablename__ = "comanda_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    comanda_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comandas.id", ondelete="CASCADE"), index=True
    )
    release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    estimated_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    received_quantity: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    comanda: Mapped["Comanda"] = relationship(back_populates="lineas")
    release: Mapped["Release"] = relationship()


class HistorialCompra(TenantScoped, Base):
    """Línia de compra històrica (dels fulls de càlcul propis, anteriors al
    sistema de Comanda/Compra). No genera stock ni toca `items`: és només
    senyal de lectura per al motor de recomanació de proveïdor — donat un
    disc que es vol comprar, quin proveïdor l'ha subministrat abans (per
    segell/artista) i amb quina recència, abans de crear una Comanda real."""

    __tablename__ = "historial_compres"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    artist: Mapped[str | None] = mapped_column(String(300), index=True)
    title: Mapped[str | None] = mapped_column(String(300), index=True)
    label: Mapped[str | None] = mapped_column(String(500), index=True)
    format: Mapped[str | None] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    # Enllaç opcional al catàleg actual, si la importació ha pogut fer el matching.
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("releases.id", ondelete="SET NULL"), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proveedor: Mapped["Proveedor"] = relationship(back_populates="historial_compres")
    release: Mapped["Release | None"] = relationship()


class EstadoSolicitud(str, enum.Enum):
    oberta = "oberta"
    resolta = "resolta"
    cancelada = "cancelada"


class OrigenSolicitud(str, enum.Enum):
    manual = "manual"
    refill_stock = "refill_stock"  # generada pel futur motor de reposició segons vendes
    peticion_cliente = "peticion_cliente"  # generada a partir d'una PeticionCliente acceptada


class SolicitudCompra(TenantScoped, Base):
    """Llista de discos que es volen comprar, sense proveïdor encara triat
    (a diferència de `Comanda`, que sempre en té un). És el punt d'entrada
    flexible del flux de compres: es pot començar aquí, o saltar-se-la i
    crear una `Comanda` directament quan ja se sap a qui es compra. Cada
    línia es 'resol' quan s'assigna a una `ComandaLinea` d'un proveïdor
    concret; la sol·licitud pot acabar repartida entre diverses comandes."""

    __tablename__ = "solicitudes_compra"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    estado: Mapped[EstadoSolicitud] = mapped_column(
        Enum(EstadoSolicitud, name="estado_solicitud"), default=EstadoSolicitud.oberta, index=True
    )
    origen: Mapped[OrigenSolicitud] = mapped_column(
        Enum(OrigenSolicitud, name="origen_solicitud"), default=OrigenSolicitud.manual, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lineas: Mapped[list["SolicitudCompraLinea"]] = relationship(
        back_populates="solicitud", cascade="all, delete-orphan", order_by="SolicitudCompraLinea.created_at"
    )
    user: Mapped["User | None"] = relationship()


class SolicitudCompraLinea(TenantScoped, Base):
    """Línia: un disc que es vol comprar. `release_id` si ja existeix al
    catàleg; si no, es descriu a mà (artista/titulo/sello/formato), com a
    l'alta d'un disc nou. `proveedor_sugerido_id` és el proveïdor
    suggerit (avui es tria a mà; en el futur, el motor de recomanació per
    historial de compres). Es resol de dues maneres possibles, mai les
    dues alhora: `comanda_linea_id` (s'ha comprat a proveïdor) o
    `item_resuelto_id` (ja hi havia un exemplar a estoc i no ha calgut
    comprar-lo)."""

    __tablename__ = "solicitud_compra_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    solicitud_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("solicitudes_compra.id", ondelete="CASCADE"), index=True
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("releases.id", ondelete="SET NULL"), index=True
    )
    artist: Mapped[str | None] = mapped_column(String(300))
    title: Mapped[str | None] = mapped_column(String(300))
    label: Mapped[str | None] = mapped_column(String(500))
    format: Mapped[str | None] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    proveedor_sugerido_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), index=True
    )
    comanda_linea_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comanda_items.id", ondelete="SET NULL"), index=True
    )
    item_resuelto_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL"), index=True
    )
    notes: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    solicitud: Mapped["SolicitudCompra"] = relationship(back_populates="lineas")
    release: Mapped["Release | None"] = relationship()
    proveedor_sugerido: Mapped["Proveedor | None"] = relationship()
    comanda_linea: Mapped["ComandaLinea | None"] = relationship()
    item_resuelto: Mapped["Item | None"] = relationship()

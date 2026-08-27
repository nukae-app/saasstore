import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid
from .stock import CondicionItem


class CanalVenta(str, enum.Enum):
    mostrador = "mostrador"
    discogs = "discogs"
    otro = "otro"


class MetodoPago(str, enum.Enum):
    efectivo = "efectivo"
    tarjeta = "tarjeta"
    bizum = "bizum"
    bono_cultural = "bono_cultural"


class VentaExterna(TenantScoped, Base):
    """Venta no realizada por la web: mostrador (TPV) o Discogs."""

    __tablename__ = "ventas_externas"
    __table_args__ = (
        # Mismo criterio que order_items: una copia de segunda mano solo se
        # vende una vez; una línea nou (stock agregado) puede aparecer en
        # varias ventas externas a lo largo del tiempo.
        Index(
            "ix_ventas_externas_item_id_unico_segona_ma", "item_id",
            unique=True,
            postgresql_where=text("condition = 'segona_ma'"),
            sqlite_where=text("condition = 'segona_ma'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    # Agrupa totes les línies venudes en una mateixa operació de TPV (venda
    # individual o cistella sencera): comparteixen el mateix `ticket_id`
    # encara que cadascuna tingui el seu propi `id`. Permet mostrar el
    # "Resum vendes" com a tiquet (capçalera: data/client/pagament/total) +
    # línies, en lloc d'una fila solta per exemplar venut. Assignat sempre
    # explícitament a erp.py (`create_venta_externa`/`_lote`), mai deixat al
    # default de la columna — si no, cada línia d'un mateix lot en tindria un
    # de diferent.
    ticket_id: Mapped[uuid.UUID] = mapped_column(index=True, default=_uuid)
    # Nullable: un "article manual" (llibre, samarreta...) no ve del catàleg
    # d'`items`, així que no té ejemplar que reservar — porta `descripcion`
    # en el seu lloc (veure abajo).
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    # Snapshot de la condición al vender (mismo criterio que en OrderItem).
    condition: Mapped[CondicionItem | None] = mapped_column(Enum(CondicionItem, name="condicion_item"))
    # Unidades vendidas. Para segona_ma siempre 1; para nou puede ser N.
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # Només per a articles manuals (item_id NULL): descripció lliure del que
    # es ven (p.ex. "Llibre - Vinyl. La biblia del col·leccionista").
    description: Mapped[str | None] = mapped_column(String(300))
    channel: Mapped[CanalVenta] = mapped_column(
        Enum(CanalVenta, name="canal_venta"), index=True
    )
    payment_method: Mapped[MetodoPago] = mapped_column(
        Enum(MetodoPago, name="metodo_pago"), default=MetodoPago.efectivo, index=True
    )
    sale_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    client_name: Mapped[str | None] = mapped_column(String(300))
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    discogs_sale_id: Mapped[int | None] = mapped_column(BigInteger)
    notes: Mapped[str | None] = mapped_column(Text)
    # NULL = pendent de cobrar (targeta/Discogs); non-NULL = cobrat (efectiu sempre immediat)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Snapshot del tipus d'IVA aplicat en el moment de la venda (nou vs segona mà/REBU).
    tipus_iva_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipus_iva.id", ondelete="SET NULL"), index=True
    )
    vat_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    vat_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    item: Mapped["Item | None"] = relationship()
    client: Mapped["User | None"] = relationship(back_populates="vendes", foreign_keys=[user_id])
    tipus_iva: Mapped["TipusIva | None"] = relationship()


class CajaSession(TenantScoped, Base):
    """Sesión de caja: apertura y cierre de un turno, con control de efectivo."""

    __tablename__ = "caja_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    opening_float: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_cash_sales: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total_cash_in: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total_cash_out: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    actual_count: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    movimientos: Mapped[list["CajaMovimiento"]] = relationship(back_populates="session", order_by="CajaMovimiento.date")


class TipoMovimiento(str, enum.Enum):
    entrada = "entrada"
    salida = "salida"


class CajaMovimiento(TenantScoped, Base):
    """Movimiento manual de caja: entrada de efectivo o salida (compra, ingreso en banco...)."""

    __tablename__ = "caja_movimientos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("caja_sessions.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[TipoMovimiento] = mapped_column(
        Enum(TipoMovimiento, name="tipo_movimiento"), index=True
    )
    concept: Mapped[str] = mapped_column(String(300))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["CajaSession"] = relationship(back_populates="movimientos")


# ---------------------------------------------------------------------------
# Comunidad: blog y agenda
# ---------------------------------------------------------------------------


class DevolucionVenta(TenantScoped, Base):
    """Devolución de una venta (web o TPV). No borra el registro original."""

    __tablename__ = "devolucions_venta"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    # Exactamente uno de los dos debe estar relleno
    order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT"), index=True
    )
    venta_externa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ventas_externas.id", ondelete="RESTRICT"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"), index=True
    )
    # Unidades devueltas. Para segona_ma siempre 1; para nou puede ser N (no
    # hace falta que coincida con toda la cantidad vendida en la línea original).
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    reason: Mapped[str] = mapped_column(Text)
    # Qué pasa con el disco: vuelve a la venta o se retira (dañado)
    item_destination: Mapped[str] = mapped_column(String(20), default="disponible")
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["Item"] = relationship()
    order_item: Mapped["OrderItem | None"] = relationship()
    venta_externa: Mapped["VentaExterna | None"] = relationship()


class DevolucionCompra(TenantScoped, Base):
    """Devolución de una compra al proveedor o particular."""

    __tablename__ = "devolucions_compra"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"), index=True
    )
    compra_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("compras.id", ondelete="SET NULL"), index=True
    )
    # Unidades devueltas al proveedor/particular. Para segona_ma siempre 1.
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    reason: Mapped[str] = mapped_column(Text)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["Item"] = relationship()
    compra: Mapped["Compra | None"] = relationship()


# ---------------------------------------------------------------------------
# Comptabilitat — despeses, banc i periodes
# ---------------------------------------------------------------------------

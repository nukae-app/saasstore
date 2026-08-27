import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid


class EstadoPeticionCliente(str, enum.Enum):
    pendent = "pendent"                    # creada pel client
    pendent_acceptacio = "pendent_acceptacio"  # l'admin ha posat preu, esperant que el client accepti
    acceptada = "acceptada"                # client ha acceptat el preu (encara no s'ha comprat res)
    rebutjada = "rebutjada"                # client ha rebutjat el preu — fi, no es compra
    en_tramit = "en_tramit"                # enllaçada a una SolicitudCompra/Comanda real
    reservada = "reservada"                # exemplar arribat, recollida a botiga sense pagar (72h)
    recollida = "recollida"                # completada (recollida o Order pagat)
    caducada = "caducada"                  # no ha respost a temps, o no ha vingut a recollir-la
    cancelada = "cancelada"


class PeticionCliente(TenantScoped, Base):
    """Petició d'un client per un disc SENSE ESTOC (ja al catàleg o no).
    No és una reserva: és una intenció de compra. Només es compra a
    proveïdor si el client accepta el preu abans (per no acabar amb estoc
    que ningú vol). Quan arriba l'exemplar: si el client paga online
    (enviament o recollida pagada), és un Order normal sense caducitat; si
    tria recollir i pagar a botiga, aquí sí que s'aplica una reserva de 72h
    sobre l'Item (veure `Item.reserved_for_peticion_id`)."""

    __tablename__ = "peticiones_cliente"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # web (creada pel client) | tienda (l'admin la crea per una trucada o un
    # client de mostrador). En 'tienda' es salta l'acceptació online del preu:
    # fijar_precio_peticion la passa directament a 'acceptada' amb entrega
    # 'recollida_paga_botiga' (veure erp.py).
    channel: Mapped[str] = mapped_column(String(20), default="web")

    # Un dels dos: disc ja catalogat sense estoc, o descripció lliure (fora de catàleg).
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("releases.id", ondelete="SET NULL"), index=True
    )
    free_artist: Mapped[str | None] = mapped_column(String(300))
    free_title: Mapped[str | None] = mapped_column(String(300))
    client_notes: Mapped[str | None] = mapped_column(Text)

    status: Mapped[EstadoPeticionCliente] = mapped_column(
        Enum(EstadoPeticionCliente, name="estado_peticion_cliente"),
        default=EstadoPeticionCliente.pendent, index=True,
    )
    estimated_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    # envio | recollida_paga_ara | recollida_paga_botiga — triat pel client en acceptar el preu.
    chosen_delivery_method: Mapped[str | None] = mapped_column(String(30))

    solicitud_compra_linea_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("solicitud_compra_items.id", ondelete="SET NULL"), index=True
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )

    admin_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="peticiones")
    release: Mapped["Release | None"] = relationship()
    solicitud_compra_linea: Mapped["SolicitudCompraLinea | None"] = relationship()
    item: Mapped["Item | None"] = relationship(foreign_keys=[item_id])
    order: Mapped["Order | None"] = relationship()

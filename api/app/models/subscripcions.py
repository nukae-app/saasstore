import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
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


class EstatSubscripcio(str, enum.Enum):
    # A l'espera de la notificació de Redsys de l'alta (captura del token
    # COF); si es denega, l'alta es descarta (veure routers/subscripcions_public.py).
    pendent_pagament = "pendent_pagament"
    activa = "activa"
    pausada = "pausada"
    cancel_lada = "cancel_lada"


class ConfiguracioSubscripcio(TenantScoped, Base):
    """Configuració general del club del disc: una fila per tenant (Fase 4
    — abans era una fila singleton fixa `id=1`, mateix arreglo que ja va
    rebre `ConfiguracioBotiga` a la Fase 1, ver `__table_args__`). No hi ha
    "plans": el client configura la seva pròpia subscripció (periodicitat,
    quantitat) dins dels valors que aquí s'ofereixen; el preu resulta de
    `preu_per_disc * quantitat`. `marge_min_pct`/`marge_max_pct` són només
    els valors per defecte del filtre a la pantalla de tria de catàleg de
    l'admin (veure routers/admin_subscripcions.py) — no filtren res
    automàticament."""

    __tablename__ = "configuracio_subscripcio"
    __table_args__ = (UniqueConstraint("tenant_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    preu_per_disc: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    marge_min_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("70"))
    marge_max_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("120"))
    periodicitats_mesos_disponibles: Mapped[list] = mapped_column(JSON, default=list)
    quantitats_disponibles: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Subscripcio(TenantScoped, Base):
    """Alta d'un client: estat, configuració pròpia (periodicitat, quantitat,
    seccions preferides) i credencial de cobrament recurrent."""

    __tablename__ = "subscripcions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    estat: Mapped[EstatSubscripcio] = mapped_column(
        Enum(EstatSubscripcio, name="estat_subscripcio"), default=EstatSubscripcio.pendent_pagament, index=True
    )
    address_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("addresses.id", ondelete="RESTRICT"))
    # Gèneres musicals (Discogs) que el client ha triat com a preferits —
    # veure `services.subscripcions.GENERES_DISCOGS` per a la llista tancada
    # d'opcions i el matching (substring sobre `Release.genero`, mateix
    # patró que el filtre del catàleg públic). Llista buida = sense
    # preferència, qualsevol gènere val. NO són `Seccio` (cubetes físiques
    # de la botiga): és un concepte diferent, tot i que abans s'hi va confondre.
    generes_preferits: Mapped[list | None] = mapped_column(JSON)
    # Cada quants mesos es factura/envia, i quants discs per enviament: triats
    # pel client a l'alta entre els valors que oferia `ConfiguracioSubscripcio`
    # en aquell moment. Fixos un cop donat d'alta (per canviar-los cal
    # cancel·lar i tornar a apuntar-se, veure routers/me.py).
    periodicitat_mesos: Mapped[int] = mapped_column(Integer)
    quantitat: Mapped[int] = mapped_column(Integer)
    # Snapshot de preu_per_disc * quantitat en el moment de l'alta (mateix
    # esperit que OrderItem.price): un canvi futur del preu no afecta
    # subscriptors ja donats d'alta.
    preu_periode: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Identificador reutilitzable que retorna Redsys (Ds_Merchant_Identifier)
    # en captar-lo amb DS_MERCHANT_IDENTIFIER=REQUIRED a l'alta; permet cobrar
    # els períodes següents servidor-a-servidor, sense redirigir el client
    # (veure services/redsys.py::charge_recurring).
    redsys_identifier: Mapped[str | None] = mapped_column(String(40))
    # Ds_Merchant_Cof_Txnid de la transacció CIT original (l'alta): identifica
    # la sèrie de cobraments recurrents davant Visa/Mastercard. S'envia a cada
    # cobrament MIT posterior (opcional per Redsys, molt recomanat).
    redsys_cof_txnid: Mapped[str | None] = mapped_column(String(40))
    proxima_facturacio: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cancel_lada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship()
    address: Mapped["Address"] = relationship()
    cobraments: Mapped[list["CobramentSubscripcio"]] = relationship(
        back_populates="subscripcio", order_by="CobramentSubscripcio.periode"
    )


class EstatCobrament(str, enum.Enum):
    # Redirecció a Redsys enviada, a l'espera de la notificació servidor-a-
    # servidor (només l'alta passa per aquí; les renovacions per COF són
    # síncrones i mai queden en aquest estat, veure services/subscripcions.py).
    pendent = "pendent"
    cobrat = "cobrat"
    fallit = "fallit"


class CobramentSubscripcio(TenantScoped, Base):
    """Un càrrec periòdic (alta o renovació): un enviament. No implica encara
    cap disc assignat: això és feina de les `Assignacio` (una per disc, tantes
    com `subscripcio.quantitat`) que pengen d'aquí un cop l'admin les ha
    revisat (veure services/subscripcions.py::facturar_subscripcio)."""

    __tablename__ = "cobraments_subscripcio"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    subscripcio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscripcions.id", ondelete="CASCADE"), index=True
    )
    periode: Mapped[date] = mapped_column(Date)
    import_: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    estat: Mapped[EstatCobrament] = mapped_column(
        Enum(EstatCobrament, name="estat_cobrament_subscripcio"), index=True
    )
    ds_order: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    raw_notification: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subscripcio: Mapped["Subscripcio"] = relationship(back_populates="cobraments")
    assignacions: Mapped[list["Assignacio"]] = relationship(back_populates="cobrament")


class EstatAssignacio(str, enum.Enum):
    proposada = "proposada"
    confirmada = "confirmada"
    omesa = "omesa"
    sense_match = "sense_match"


class Assignacio(TenantScoped, Base):
    """Quin disc concret correspon a un dels N discs d'un cobrament (enviament)
    ja fet: `cobrament_id` ja NO és únic, un cobrament té tantes `Assignacio`
    com `subscripcio.quantitat`. `proposada` la crea l'algorisme automàtic
    (veure services/subscripcions.py), triant només entre els exemplars que
    l'admin ha marcat com a elegibles (`Item.subscription_pool`); l'admin la
    revisa, la reassigna o confirma tot el cobrament d'un cop (moment en què
    es genera un únic `Order` amb totes les línies, mateix circuit que
    qualsevol altra venda web)."""

    __tablename__ = "subscripcio_assignacions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    cobrament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cobraments_subscripcio.id", ondelete="CASCADE"), index=True
    )
    subscripcio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscripcions.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"))
    # Denormalitzat perquè l'exclusió d'historial ("no repetir aquest àlbum")
    # sobrevisqui encara que l'item s'esborri o es retiri del catàleg.
    release_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("releases.id", ondelete="SET NULL"), index=True)
    estat: Mapped[EstatAssignacio] = mapped_column(
        Enum(EstatAssignacio, name="estat_assignacio"), default=EstatAssignacio.proposada, index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cobrament: Mapped["CobramentSubscripcio"] = relationship(back_populates="assignacions")
    subscripcio: Mapped["Subscripcio"] = relationship()
    item: Mapped["Item | None"] = relationship(foreign_keys=[item_id])
    release: Mapped["Release | None"] = relationship()
    order: Mapped["Order | None"] = relationship()


# ---------------------------------------------------------------------------
# Reservas de stock agregado (solo condicion='nou')
# ---------------------------------------------------------------------------

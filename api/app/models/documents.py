"""Documents comercials no fiscals: pressupostos i albarans (Bloc B1 del pla
de paritat amb Holded, veure docs/PLAN_PARIDAD_HOLDED.md). Cap dels dos és
un document fiscal amb numeració legal protegida — a diferència de la
futura factura de venda (B2), no calen les cauteles de VeriFactu."""

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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid


class DocumentCounter(TenantScoped, Base):
    """Comptador correlatiu per any fiscal, compartit per tots els tipus de
    document comercial (`document_type`: "pressupost", "albara", i en el
    futur "factura") — mateix criteri d'atomicitat que
    `JournalEntryCounter` (UPDATE condicionat, mai SELECT+UPDATE): un
    número duplicat o amb buits és un problema legal/de negoci, no només un
    bug. Una sola taula genèrica en lloc d'un comptador per tipus evita
    triplicar aquesta lògica quan arribi B2 (factura de venda)."""

    __tablename__ = "document_comptadors"
    __table_args__ = (UniqueConstraint("tenant_id", "document_type", "fiscal_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_type: Mapped[str] = mapped_column(String(30), index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    next_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class PressupostStatus(str, enum.Enum):
    esborrany = "esborrany"
    enviat = "enviat"
    acceptat = "acceptat"
    rebutjat = "rebutjat"
    caducat = "caducat"


class Pressupost(TenantScoped, Base):
    """Presupuesto de venta. El client es guarda com a snapshot (mateix
    criteri que `Order`: `user_id` nullable + camps copiats) perquè es pot
    pressupostar algú que encara no té compte, i perquè un pressupost
    històric no ha de canviar si el client actualitza les seves dades més
    endavant."""

    __tablename__ = "pressupostos"
    __table_args__ = (UniqueConstraint("tenant_id", "fiscal_year", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[PressupostStatus] = mapped_column(
        Enum(PressupostStatus, name="pressupost_status"),
        default=PressupostStatus.esborrany, server_default="esborrany", index=True,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    client_name: Mapped[str] = mapped_column(String(200))
    client_email: Mapped[str | None] = mapped_column(String(320))
    client_address: Mapped[dict | None] = mapped_column(JSON)

    issue_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    valid_until: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    # Es fixa quan s'accepta el pressupost i es converteix en pedido — es
    # reutilitza `Order` tal qual, no hi ha un "pedido tipus pressupost".
    converted_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["PressupostLinia"]] = relationship(
        back_populates="pressupost", cascade="all, delete-orphan", order_by="PressupostLinia.position"
    )


class PressupostLinia(TenantScoped, Base):
    """Línia lliure (descripció + preu), no lligada a `Release`/`Item` del
    catàleg — un pressupost pot incloure un servei o un article que encara
    no està d'alta."""

    __tablename__ = "pressupost_linies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    pressupost_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pressupostos.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1"), server_default="1")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    vat_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("21"), server_default="21")

    pressupost: Mapped["Pressupost"] = relationship(back_populates="lines")


class Albara(TenantScoped, Base):
    """Albarà d'entrega. v1 = sempre 1:1 amb un `Order` (tot el pedido
    s'entrega junt, `order_id` únic) — l'entrega parcial en diversos
    albarans per pedido queda fora d'abast a propòsit (veure
    docs/PLAN_PARIDAD_HOLDED.md, bloc B1): no hi ha cap cas d'ús real
    conegut i afegiria haver de trackejar quines línies ja s'han entregat."""

    __tablename__ = "albarans"
    __table_args__ = (UniqueConstraint("tenant_id", "fiscal_year", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    number: Mapped[int] = mapped_column(Integer)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, unique=True
    )
    delivery_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship()

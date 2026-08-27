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


class CategoriaDespesa(str, enum.Enum):
    compres_material = "compres_material"        # discos (vinculat a Compra)
    subministraments = "subministraments"        # llum, aigua, gas
    lloguer = "lloguer"
    comunicacions = "comunicacions"              # telèfon, internet
    serveis_professionals = "serveis_professionals"
    transport = "transport"
    material_oficina = "material_oficina"
    publicitat = "publicitat"
    altres = "altres"


class EstatPagamentDespesa(str, enum.Enum):
    pendent = "pendent"
    pagat = "pagat"
    vencut = "vencut"


class EstatConciliacio(str, enum.Enum):
    pendent = "pendent"
    conciliat = "conciliat"
    ignorat = "ignorat"   # transferència entre comptes propis, etc.


class TipusIva(TenantScoped, Base):
    """Tipus d'IVA configurables: percentatge i quin règim representen.

    `per_defecte_nou` / `per_defecte_segona_ma` marquen quin tipus s'aplica
    automàticament a una venda segons `Item.condition` (només n'hi pot haver
    un actiu de cada a la vegada, validat a l'endpoint). A compra es tria
    sempre a mà entre els tipus actius.
    """

    __tablename__ = "tipus_iva"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Fase 4 Etapa B: atributo Python en inglés, ya alineado con el nombre
    # de columna que fijó la Etapa A.
    name: Mapped[str] = mapped_column(String(200))
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # Règim especial de béns usats: l'IVA es calcula sobre el marge (venda - cost), no sobre el preu.
    is_rebu: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    default_new: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    default_used: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Despesa(TenantScoped, Base):
    """Factura de despesa: discos (compres_material) o serveis generals (llum, gestor...)."""

    __tablename__ = "despeses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    invoice_number: Mapped[str | None] = mapped_column(String(200), index=True)
    invoice_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)

    proveidor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    supplier_name: Mapped[str] = mapped_column(String(300))  # sempre informat (copiat o manual)

    category: Mapped[CategoriaDespesa] = mapped_column(
        Enum(CategoriaDespesa, name="categoria_despesa"), index=True
    )
    concept: Mapped[str] = mapped_column(String(500))

    taxable_base: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    tipus_iva_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipus_iva.id", ondelete="SET NULL"), index=True
    )
    vat_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))    # snapshot del percentatge triat
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    payment_status: Mapped[EstatPagamentDespesa] = mapped_column(
        Enum(EstatPagamentDespesa, name="estat_pagament_despesa"),
        default=EstatPagamentDespesa.pendent, index=True
    )
    payment_date: Mapped[date | None] = mapped_column(Date)
    # transferencia | rebut_domiciliat | targeta | efectiu | paypal_altres
    payment_method: Mapped[str | None] = mapped_column(String(30))

    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proveidor: Mapped["Proveedor | None"] = relationship(back_populates="despeses", foreign_keys=[proveidor_id])
    # Una factura de proveïdor pot cobrir diverses recepcions (Compra); cadascuna
    # només pot pertànyer a una factura (vegeu Compra.despesa_id).
    compras: Mapped[list["Compra"]] = relationship(back_populates="despesa")
    moviments: Mapped[list["MovimentBancari"]] = relationship(back_populates="despesa")
    tipus_iva: Mapped["TipusIva | None"] = relationship()


class CompteBancari(TenantScoped, Base):
    """Compte bancari de l'empresa."""

    __tablename__ = "comptes_bancaris"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    iban: Mapped[str | None] = mapped_column(String(34))
    bank: Mapped[str | None] = mapped_column(String(100))   # "CaixaBank", "BBVA"...
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    opening_balance_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    moviments: Mapped[list["MovimentBancari"]] = relationship(
        back_populates="compte", order_by="MovimentBancari.operation_date"
    )


class MovimentBancari(TenantScoped, Base):
    """Línia d'extracte bancari. Concilia amb despeses, vendes web o vendes externes."""

    __tablename__ = "moviments_bancaris"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    compte_id: Mapped[int] = mapped_column(
        ForeignKey("comptes_bancaris.id", ondelete="RESTRICT"), index=True
    )
    operation_date: Mapped[date] = mapped_column(Date, index=True)
    value_date: Mapped[date | None] = mapped_column(Date)
    concept: Mapped[str] = mapped_column(String(500))
    movement_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # + ingrés / - despesa
    balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    status: Mapped[EstatConciliacio] = mapped_column(
        Enum(EstatConciliacio, name="estat_conciliacio"),
        default=EstatConciliacio.pendent, index=True
    )
    # Un sol d'aquests quan conciliat
    despesa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("despeses.id", ondelete="SET NULL"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )
    venta_externa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ventas_externas.id", ondelete="SET NULL"), index=True
    )
    reconciliation_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    compte: Mapped["CompteBancari"] = relationship(back_populates="moviments")
    despesa: Mapped["Despesa | None"] = relationship(back_populates="moviments", foreign_keys=[despesa_id])
    order: Mapped["Order | None"] = relationship(foreign_keys=[order_id])
    venta_externa: Mapped["VentaExterna | None"] = relationship(foreign_keys=[venta_externa_id])


class PeriodeComptable(TenantScoped, Base):
    """Mes comptable. Quan 'tancat=True' el mes es considera revisat i aprovat."""

    __tablename__ = "periodes_comptables"
    __table_args__ = (UniqueConstraint("tenant_id", "year", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer, index=True)    # 1-12
    closed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaixaDiaria(TenantScoped, Base):
    """Full de caixa diària: cobraments manuals per mètode de pagament i tipus
    d'IVA, un registre per dia. És l'equivalent digital de l'Excel que portava
    la botiga per quadrar caixa cada dia — no es deriva de `VentaExterna`/`Order`
    (aquestes no distingeixen Bizum/Paypal/Bono cultural ni el desglossament per
    IVA per mètode), s'omple a mà des de `/admin/resultat`."""

    __tablename__ = "caixa_diaria"
    __table_args__ = (UniqueConstraint("tenant_id", "date"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    date: Mapped[date] = mapped_column(Date, index=True)

    card_21: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    card_4: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    cash_21: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    cash_4: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    bizum_21: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    bizum_4: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    paypal_21: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    paypal_4: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    transfer_21: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    cultural_voucher: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

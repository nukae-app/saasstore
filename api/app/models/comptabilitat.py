import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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
    # Comissió bancària facturada a part (mode `cobrament_apart` de
    # `ComissioPagament`) — quan el banc no la dedueix del cobrament sinó
    # que la carrega com una factura/càrrec periòdic propi.
    comissions_bancaries = "comissions_bancaries"
    altres = "altres"


class EstatPagamentDespesa(str, enum.Enum):
    pendent = "pendent"
    # Inclosa en una RemesaPagament ja generada (fitxer SEPA pain.001 pujat
    # al banc), a l'espera que s'executi de veritat — evita que la mateixa
    # despesa es colgui en una segona remesa mentre s'espera (ver
    # docs/PLAN_COBRAMENTS_PAGAMENTS.md). Passa a `pagat` quan es concilia,
    # línia a línia o contra tota la remesa segons com liquidi el banc.
    en_remesa = "en_remesa"
    pagat = "pagat"
    vencut = "vencut"


class EstatConciliacio(str, enum.Enum):
    pendent = "pendent"
    conciliat = "conciliat"
    ignorat = "ignorat"   # transferència entre comptes propis, etc.


class DestinoIva(str, enum.Enum):
    """A quina activitat es destina una Despesa, per calcular correctament
    l'IVA deduïble sota prorrata especial (art. 103.Dos.1º LIVA) — ver
    docs/PLAN_MODELO303_FITXER.md. `activitat_gravada` és el valor per
    defecte i reprodueix el comportament actual (deducció 100%) per a qui
    no fa servir prorrata."""
    activitat_gravada = "activitat_gravada"
    activitat_exempta = "activitat_exempta"
    comu = "comu"


class RetencioTipus(str, enum.Enum):
    """Quina casella d'AEAT alimenta la retenció d'IRPF practicada en una
    Despesa: professional (factures de professionals -> Model 111) o lloguer
    (lloguer del local a arrendador persona física -> Model 115). No hi ha
    `treball` perquè aquest negoci no modela nòmines (ver docs/PLAN_PARIDAD_HOLDED.md)."""
    professional = "professional"
    lloguer = "lloguer"


class AccountType(str, enum.Enum):
    actiu = "actiu"
    passiu = "passiu"
    patrimoni_net = "patrimoni_net"
    ingres = "ingres"
    despesa = "despesa"


class AccountingAccount(TenantScoped, Base):
    """Compte del pla general comptable, sembrat per tenant a la creació
    segons la seva jurisdicció (`Tenant.accounting_jurisdiction_id`, ver
    platform.py::AccountingJurisdiction) i forma jurídica
    (`ConfiguracioBotiga.legal_form`) — ver services/comptabilitat_seed.py.

    `group`/`account_type` es guarden explícits en comptes de derivar-se del
    primer dígit de `code` en cada query — mateix criteri que `Despesa.vat_pct`
    guarda l'snapshot del percentatge en comptes de recalcular-lo, perquè els
    informes de fase 3 (Balanç de Situació / PyG) siguin un simple
    `WHERE account_type IN (...)`.

    No es modela el tercer (proveïdor/client) com a subcompte explotat
    (400001, 400002...): això és `JournalLine.counterparty_id` (fase 2), no
    una fila més aquí."""

    __tablename__ = "comptes_comptables"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), index=True)  # "570", "4750"...
    name: Mapped[str] = mapped_column(String(200))
    group: Mapped[int] = mapped_column(Integer, index=True)  # 1-7, primer dígit del pla de comptes
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType, name="account_type"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
    # Operació exempta d'IVA (no és el mateix que un 0% gravat: l'exempta no
    # dona dret a deduir directament l'IVA suportat atribuïble) — necessari
    # per a la prorrata especial, ver docs/PLAN_MODELO303_FITXER.md.
    exempt: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
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
    destino_iva: Mapped[DestinoIva] = mapped_column(
        Enum(DestinoIva, name="destino_iva"),
        default=DestinoIva.activitat_gravada, server_default="activitat_gravada", index=True,
    )
    # Compra a fora de la UE amb el règim de diferiment de l'IVA a la
    # importació ja donat d'alta a Duanes: l'IVA d'aquesta despesa es
    # reconeix a la casella 77 del Model 303 (autoliquidat, neutre de
    # tresoreria), no com a IVA suportat normal (28/29) — ver
    # docs/PLAN_MODELO303_FITXER.md.
    importacio_diferida: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Retenció d'IRPF practicada al proveïdor (Model 111/115) — ver RetencioTipus.
    # `retencio_import` és sempre un snapshot (base * pct/100), mai recalculat en
    # llegir, mateix criteri que vat_amount. `total` NO descompta la retenció: és
    # l'import de la factura; el que realment surt del banc és `total - retencio_import`
    # (ver post_despesa_alta, que ho parteix entre 400 i 4751).
    retencio_tipus: Mapped[RetencioTipus | None] = mapped_column(
        Enum(RetencioTipus, name="retencio_tipus"), index=True
    )
    retencio_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    retencio_import: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    payment_status: Mapped[EstatPagamentDespesa] = mapped_column(
        Enum(EstatPagamentDespesa, name="estat_pagament_despesa"),
        default=EstatPagamentDespesa.pendent, index=True
    )
    payment_date: Mapped[date | None] = mapped_column(Date)
    # transferencia | rebut_domiciliat | targeta | efectiu | paypal_altres
    payment_method: Mapped[str | None] = mapped_column(String(30))

    notes: Mapped[str | None] = mapped_column(Text)
    # Justificant original (factura del proveïdor en PDF), si es té — via
    # importació OCR (DespesaImport) o penjat directament en l'alta manual.
    # Mai obligatori: moltes despeses antigues o donades d'alta a mà no en tenen.
    source_document_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proveidor: Mapped["Proveedor | None"] = relationship(back_populates="despeses", foreign_keys=[proveidor_id])
    # Una factura de proveïdor pot cobrir diverses recepcions (Compra); cadascuna
    # només pot pertànyer a una factura (vegeu Compra.despesa_id).
    compras: Mapped[list["Compra"]] = relationship(back_populates="despesa")
    moviments: Mapped[list["MovimentBancari"]] = relationship(back_populates="despesa")
    tipus_iva: Mapped["TipusIva | None"] = relationship()
    despesa_import: Mapped["DespesaImport | None"] = relationship(back_populates="despesa", uselist=False)


class DespesaImportStatus(str, enum.Enum):
    pendent = "pendent"        # pujat, extracció encara no llançada o en curs
    processat = "processat"    # la IA ha tornat dades, pendent de revisió humana
    error = "error"            # ha fallat l'extracció (PDF il·legible, timeout...)
    confirmat = "confirmat"    # revisat i convertit en Despesa
    descartat = "descartat"    # descartat sense crear cap Despesa


class DespesaImport(TenantScoped, Base):
    """Cua de revisió per a l'alta de Despeses a partir d'un PDF de factura.

    `extracted_data` és sempre un ESBORRANY (JSON, no columnes tipades):
    el que ha llegit la IA, mai dades contables definitives — només serveix
    per prellenar el formulari de `Despesa`, que és qui valida i contabilitza
    de veritat. Veure services/despesa_extraction.py."""

    __tablename__ = "despesa_imports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    file_url: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(300))
    status: Mapped[DespesaImportStatus] = mapped_column(
        Enum(DespesaImportStatus, name="despesa_import_status"),
        default=DespesaImportStatus.pendent, server_default="pendent", index=True,
    )
    extracted_data: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    despesa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("despeses.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    despesa: Mapped["Despesa | None"] = relationship(back_populates="despesa_import")


class CompteBancari(TenantScoped, Base):
    """Compte bancari de l'empresa."""

    __tablename__ = "comptes_bancaris"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    iban: Mapped[str | None] = mapped_column(String(34))
    bank: Mapped[str | None] = mapped_column(String(100))   # "CaixaBank", "BBVA"...
    # Opcional: ja no és obligatori per a transferències SEPA dins la UE des
    # de 2012/2016, però convé informar-lo si es coneix (algunes remeses
    # pain.001 el fan servir per al DbtrAgt) — ver services/sepa_pain001.py.
    bic: Mapped[str | None] = mapped_column(String(11))
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
    # Quart "un sol d'aquests quan conciliat": quan el banc liquida tota una
    # remesa de pagament (SEPA pain.001) en un únic càrrec, en lloc d'una
    # línia per proveïdor — ver docs/PLAN_COBRAMENTS_PAGAMENTS.md i
    # routers/comptabilitat/banc.py::conciliar_moviment.
    remesa_pagament_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("remeses_pagament.id", ondelete="SET NULL"), index=True
    )
    reconciliation_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    compte: Mapped["CompteBancari"] = relationship(back_populates="moviments")
    despesa: Mapped["Despesa | None"] = relationship(back_populates="moviments", foreign_keys=[despesa_id])
    order: Mapped["Order | None"] = relationship(foreign_keys=[order_id])
    venta_externa: Mapped["VentaExterna | None"] = relationship(foreign_keys=[venta_externa_id])
    remesa_pagament: Mapped["RemesaPagament | None"] = relationship(foreign_keys=[remesa_pagament_id])


class ReglaConciliacio(TenantScoped, Base):
    """Regla de conciliació bancària automàtica (Bloc B3, veure
    docs/PLAN_PARIDAD_HOLDED.md): si el concepte d'un moviment conté
    `pattern` (substring, sense distingir majúscules), es restringeix la
    cerca de despeses candidates al `proveidor`. Coincidència per substring
    simple, no regex — més fàcil de mantenir per un admin no tècnic i prou
    per al cas d'ús real (proveïdors recurrents amb un concepte estable a
    l'extracte, tipus "AMAZON" o "ENDESA ENERGIA")."""

    __tablename__ = "regles_conciliacio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern: Mapped[str] = mapped_column(String(200))
    proveidor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proveedores.id", ondelete="CASCADE"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proveidor: Mapped["Proveedor"] = relationship()


class RemesaPagamentStatus(str, enum.Enum):
    generada = "generada"
    anullada = "anullada"


class RemesaPagament(TenantScoped, Base):
    """Remesa de pagament a proveïdors (fitxer SEPA pain.001.001.03,
    transferència — NO domiciliació) — ver docs/PLAN_COBRAMENTS_PAGAMENTS.md.

    NOMÉS genera el fitxer; mai l'envia al banc (això seria un servei PISP,
    mateixa paret regulatòria que l'AISP descartat per a la conciliació
    automàtica — ver el mateix document). L'admin sempre puja el XML a mà
    al portal del seu banc.

    `xml_content` es guarda tal qual es va generar i mai es torna a crear:
    un cop `generada`, és immutable (mateix criteri que `Factura` un cop
    `emesa`) — per corregir alguna cosa cal anul·lar-la i generar-ne una de
    nova, no editar-la. El tancament real (marcar les `Despesa` `pagat`) NO
    passa per aquí: és la conciliació bancària de sempre (línia a línia, o
    contra tota la remesa si el banc liquida en bloc — ver `MovimentBancari.
    remesa_pagament_id`), mai un botó de "confirmar remesa" apart."""

    __tablename__ = "remeses_pagament"
    __table_args__ = (UniqueConstraint("tenant_id", "fiscal_year", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[RemesaPagamentStatus] = mapped_column(
        Enum(RemesaPagamentStatus, name="remesa_pagament_status"),
        default=RemesaPagamentStatus.generada, server_default="generada", index=True,
    )
    compte_bancari_id: Mapped[int] = mapped_column(ForeignKey("comptes_bancaris.id", ondelete="RESTRICT"), index=True)
    execution_date: Mapped[date] = mapped_column(Date)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    xml_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    compte_bancari: Mapped["CompteBancari"] = relationship()
    lines: Mapped[list["RemesaPagamentLinia"]] = relationship(
        back_populates="remesa", cascade="all, delete-orphan", order_by="RemesaPagamentLinia.position"
    )


class RemesaPagamentLinia(TenantScoped, Base):
    """Una `Despesa` dins d'una remesa. `import_` és sempre el NET
    (`Despesa.total - Despesa.retencio_import`) — el que de veritat surt cap
    al proveïdor si hi ha retenció d'IRPF practicada (la part retinguda no
    se li transfereix, es deu a Hisenda, ver `post_despesa_alta`), mateix
    criteri que ja fa servir `rank_despesa_candidates`."""

    __tablename__ = "remesa_pagament_linies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    remesa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("remeses_pagament.id", ondelete="CASCADE"), index=True)
    despesa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("despeses.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    import_: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    end_to_end_id: Mapped[str] = mapped_column(String(35))

    remesa: Mapped["RemesaPagament"] = relationship(back_populates="lines")
    despesa: Mapped["Despesa"] = relationship()


class CanalComissio(str, enum.Enum):
    """Canal de cobrament amb targeta al qual pot aplicar una comissió
    bancària diferent — cadascun es liquida per una via diferent (ver
    docs/PLAN_COBRAMENTS_PAGAMENTS.md): `web_targeta` es tanca sol en
    confirmar Redsys, `mostrador_targeta` es tanca via caixa diària,
    `club_targeta` és el cobrament recurrent COF/MIT del Club del disc."""
    web_targeta = "web_targeta"
    mostrador_targeta = "mostrador_targeta"
    club_targeta = "club_targeta"


class ModeComissio(str, enum.Enum):
    # El banc ingressa el cobrament ja net de comissió — es reconeix la
    # comissió (626) al mateix moment de tancar el 430.
    deduccio = "deduccio"
    # El banc ingressa el cobrament íntegre; la comissió es factura o es
    # carrega a part, més tard — es tracta com una Despesa normal
    # (categoria `comissions_bancaries`), no toca el tancament del cobrament.
    cobrament_apart = "cobrament_apart"


class ComissioPagament(TenantScoped, Base):
    """Configuració de comissió bancària per canal de cobrament amb
    targeta — un tenant pot tenir un mode diferent per canal (p. ex. Redsys
    web en `deduccio` i el datàfon de mostrador en `cobrament_apart`), i
    fins i tot no tenir cap fila per a un canal (equival a comissió zero).
    Sense historial de canvis a propòsit: si canvia la comissió pactada amb
    el banc, s'edita la fila existent — mateix nivell de simplicitat que
    `TipusIva`/`TramEnviament`."""

    __tablename__ = "comissions_pagament"
    __table_args__ = (UniqueConstraint("tenant_id", "canal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canal: Mapped[CanalComissio] = mapped_column(Enum(CanalComissio, name="canal_comissio"), index=True)
    mode: Mapped[ModeComissio] = mapped_column(Enum(ModeComissio, name="mode_comissio"))
    pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), server_default="0")
    fixed_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IvaCompensacioPendent(TenantScoped, Base):
    """Quota d'IVA pendent de compensar (casella [87] del Model 303) que un
    trimestre trasllada al següent — ver docs/PLAN_MODELO303_FITXER.md. Es
    desa NOMÉS en generar el fitxer d'un trimestre amb `tipo_declaracion=
    "C"` i resultat negatiu; el trimestre següent llegeix el registre
    anterior com la seva casella [110]. No es recalcula sol."""

    __tablename__ = "iva_compensacio_pendent"
    __table_args__ = (UniqueConstraint("tenant_id", "fiscal_year", "trimestre"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    trimestre: Mapped[int] = mapped_column(Integer)
    import_pendent: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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


class JournalSourceType(str, enum.Enum):
    venda_web = "venda_web"
    venda_externa = "venda_externa"
    despesa_alta = "despesa_alta"
    despesa_pagament = "despesa_pagament"
    caixa_diaria = "caixa_diaria"
    actiu_alta = "actiu_alta"
    actiu_amortitzacio = "actiu_amortitzacio"
    manual = "manual"
    tancament_exercici = "tancament_exercici"
    factura_manual = "factura_manual"


class JournalEntryCounter(TenantScoped, Base):
    """Comptador correlatiu d'assentaments per any fiscal — requisit legal
    del Libro Diario (numeració sense buits ni duplicats). S'actualitza amb
    un UPDATE condicionat, mai amb un SELECT previ seguit d'UPDATE — mateix
    criteri que services/reservations.py per a la reserva atòmica
    d'exemplars, aquí perquè un número duplicat és un problema legal, no
    només un bug de negoci."""

    __tablename__ = "assentament_comptadors"
    __table_args__ = (UniqueConstraint("tenant_id", "fiscal_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    next_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class JournalEntry(TenantScoped, Base):
    """Assentament de partida doble. `source_type`/`source_id` apunten al
    document de negoci que el va originar (venda, despesa, conciliació...);
    `source_id` NO és una FK real perquè cada `source_type` apunta a una
    taula diferent (i `manual` a cap). La invariant sum(debit)==sum(credit)
    de les seves línies es garanteix al servei
    (services/comptabilitat_posting.py::post_entry), no a l'esquema —
    Postgres no pot expressar-la com a CHECK entre files."""

    __tablename__ = "assentaments"
    __table_args__ = (UniqueConstraint("tenant_id", "fiscal_year", "entry_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    entry_number: Mapped[int] = mapped_column(Integer)
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[JournalSourceType] = mapped_column(
        Enum(JournalSourceType, name="journal_source_type"), index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    period_id: Mapped[int | None] = mapped_column(
        ForeignKey("periodes_comptables.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["JournalLine"]] = relationship(back_populates="entry", cascade="all, delete-orphan")


class JournalLine(TenantScoped, Base):
    """Línia d'un assentament: exactament un de `debit`/`credit` és > 0
    (mai els dos, mai cap dels dos) — `ck_apunts_debit_xor_credit`."""

    __tablename__ = "apunts"
    __table_args__ = (
        CheckConstraint("(debit = 0 AND credit > 0) OR (debit > 0 AND credit = 0)", name="ck_apunts_debit_xor_credit"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assentaments.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("comptes_comptables.id", ondelete="RESTRICT"), index=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    description: Mapped[str | None] = mapped_column(String(500))
    punteat: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    punteat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    punteat_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["AccountingAccount"] = relationship()
    punteat_by: Mapped["User | None"] = relationship()

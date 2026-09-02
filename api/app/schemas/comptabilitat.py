import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class TipusIvaIn(BaseModel):
    name: str
    percentage: Decimal
    is_rebu: bool = False
    default_new: bool = False
    default_used: bool = False
    active: bool = True


class TipusIvaUpdate(BaseModel):
    name: str | None = None
    percentage: Decimal | None = None
    is_rebu: bool | None = None
    default_new: bool | None = None
    default_used: bool | None = None
    active: bool | None = None


class TipusIvaOut(BaseModel):
    id: int
    name: str
    percentage: Decimal
    is_rebu: bool
    default_new: bool
    default_used: bool
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


CATEGORIES_DESPESA = Literal[
    "compres_material", "subministraments", "lloguer", "comunicacions",
    "serveis_professionals", "transport", "material_oficina", "publicitat", "altres"
]


ESTATS_PAGAMENT = Literal["pendent", "pagat", "vencut"]


METODES_PAGAMENT_DESPESA = Literal["transferencia", "rebut_domiciliat", "targeta", "efectiu", "paypal_altres"]


class DespesaIn(BaseModel):
    invoice_number: str | None = None
    invoice_date: date
    due_date: date | None = None
    proveidor_id: uuid.UUID | None = None
    supplier_name: str
    category: CATEGORIES_DESPESA
    concept: str
    taxable_base: Decimal
    tipus_iva_id: int | None = None        # si s'indica, el seu percentatge mana sobre vat_pct
    vat_pct: Decimal = Decimal("21.00")
    total: Decimal | None = None           # si None, es calcula: base + base*vat_pct/100
    payment_status: ESTATS_PAGAMENT = "pendent"
    payment_date: date | None = None
    payment_method: METODES_PAGAMENT_DESPESA | None = None
    notes: str | None = None

    @computed_field
    @property
    def vat_amount(self) -> Decimal:
        return (self.taxable_base * self.vat_pct / 100).quantize(Decimal("0.01"))


class DespesaUpdate(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    proveidor_id: uuid.UUID | None = None
    supplier_name: str | None = None
    category: CATEGORIES_DESPESA | None = None
    concept: str | None = None
    taxable_base: Decimal | None = None
    tipus_iva_id: int | None = None
    vat_pct: Decimal | None = None
    vat_amount: Decimal | None = None
    total: Decimal | None = None
    payment_status: ESTATS_PAGAMENT | None = None
    payment_date: date | None = None
    payment_method: METODES_PAGAMENT_DESPESA | None = None
    notes: str | None = None


class DespesaOut(BaseModel):
    id: uuid.UUID
    invoice_number: str | None
    invoice_date: date
    due_date: date | None
    proveidor_id: uuid.UUID | None
    supplier_name: str
    category: str
    concept: str
    taxable_base: Decimal
    tipus_iva_id: int | None
    vat_pct: Decimal
    vat_amount: Decimal
    total: Decimal
    payment_status: str
    payment_date: date | None
    payment_method: str | None
    compra_ids: list[uuid.UUID] = []
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DespesaDesDeComprasIn(BaseModel):
    """Crea una factura de proveïdor que cobreix una o més recepcions (Compra)
    encara no facturades. El total i l'IVA es calculen a partir del cost
    d'adquisició dels items de les compres seleccionades."""
    compra_ids: list[uuid.UUID] = Field(min_length=1)
    invoice_number: str | None = None
    invoice_date: date | None = None
    tipus_iva_id: int | None = None
    notes: str | None = None


# --- Comptabilitat: Comptes bancaris ---


class CompteBancariIn(BaseModel):
    name: str
    iban: str | None = None
    bank: str | None = None
    opening_balance: Decimal = Decimal("0")
    opening_balance_date: date | None = None


class CompteBancariOut(BaseModel):
    id: int
    name: str
    iban: str | None
    bank: str | None
    active: bool
    opening_balance: Decimal
    opening_balance_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Comptabilitat: Moviments bancaris ---


class MovimentBancariOut(BaseModel):
    id: uuid.UUID
    compte_id: int
    operation_date: date
    value_date: date | None
    concept: str
    movement_amount: Decimal
    balance: Decimal | None
    status: str
    despesa_id: uuid.UUID | None
    order_id: uuid.UUID | None
    venta_externa_id: uuid.UUID | None
    reconciliation_notes: str | None
    created_at: datetime
    # Enriquit
    despesa_concepte: str | None = None
    despesa_proveidor: str | None = None

    model_config = {"from_attributes": True}


class ConciliarMovimentIn(BaseModel):
    status: Literal["conciliat", "ignorat"]
    despesa_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    venta_externa_id: uuid.UUID | None = None
    reconciliation_notes: str | None = None


# --- Comptabilitat: Reports ---


class ResultatLiniaDespesa(BaseModel):
    categoria: str
    total: Decimal
    num_factures: int


class ResultatMensualOut(BaseModel):
    year: int
    mes: int
    periode_tancat: bool
    # Ingressos
    vendes_web: Decimal
    vendes_mostrador: Decimal
    vendes_discogs: Decimal
    total_ingressos: Decimal
    # Cost de les vendes (COGS — imputat al mes que es ven, no al mes de compra)
    cogs_web: Decimal
    cogs_extern: Decimal
    total_cogs: Decimal
    items_sense_cost: int        # vendes sense coste_adquisicion informat
    # Marge brut = ingressos − COGS
    marge_brut: Decimal
    # Despeses operatives (exclou compres_material, que ja van al COGS)
    despeses: list[ResultatLiniaDespesa]
    total_despeses_operatives: Decimal
    # Per compatibilitat — total de totes les despeses de la taula Despesa del mes
    total_despeses: Decimal
    # Resultat net = marge_brut − despeses_operatives
    resultat: Decimal


class IVALiniaOut(BaseModel):
    categoria: str
    base: Decimal
    iva_pct: Decimal
    iva_import: Decimal


class IVATrimestralOut(BaseModel):
    year: int
    trimestre: int           # 1-4
    mesos: list[int]         # [1,2,3] per T1, etc.
    # IVA suportat (despeses — deductible)
    iva_suportat: list[IVALiniaOut]
    total_base_suportat: Decimal
    total_iva_suportat: Decimal
    # IVA repercutit (vendes — a ingressar)
    iva_repercutit: list[IVALiniaOut]
    total_base_repercutit: Decimal
    total_iva_repercutit: Decimal
    # Resultat net
    resultat_iva: Decimal    # repercutit - suportat (+ = a pagar, - = a compensar)
    nota_rebu: bool          # True si hi ha vendes REBU que cal gestionar a part


# --- Comptabilitat: Periodes ---


class PeriodeComptableOut(BaseModel):
    id: int
    year: int
    month: int
    closed: bool
    closed_at: datetime | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Comptabilitat: Caixa diària ---


CAIXA_DIARIA_CAMPS = (
    "card_21", "card_4", "cash_21", "cash_4",
    "bizum_21", "bizum_4", "paypal_21", "paypal_4",
    "transfer_21", "cultural_voucher",
)


class CaixaDiariaLiniaIn(BaseModel):
    date: date
    card_21: Decimal = Decimal("0")
    card_4: Decimal = Decimal("0")
    cash_21: Decimal = Decimal("0")
    cash_4: Decimal = Decimal("0")
    bizum_21: Decimal = Decimal("0")
    bizum_4: Decimal = Decimal("0")
    paypal_21: Decimal = Decimal("0")
    paypal_4: Decimal = Decimal("0")
    transfer_21: Decimal = Decimal("0")
    cultural_voucher: Decimal = Decimal("0")


class CaixaDiariaLiniaOut(CaixaDiariaLiniaIn):
    total_dia: Decimal


class CaixaDiariaMesOut(BaseModel):
    year: int
    mes: int
    periode_tancat: bool
    dies: list[CaixaDiariaLiniaOut]
    totals: CaixaDiariaLiniaOut
    total_mes: Decimal


class VendesRealsLiniaOut(BaseModel):
    """Cobraments reals reconstruïts a partir de vendes web (Redsys, sempre
    targeta) i TPV mostrador (targeta/efectiu/bizum/bono cultural, segons el
    que es va triar en cobrar) — veure GET .../caixa-diaria/{y}/{m}/vendes-reals.
    Paypal i transferència no es registren enlloc a l'app (no hi ha cap
    mètode de pagament així al checkout ni al TPV), per això no apareixen
    aquí i es continuen omplint a mà."""

    date: date
    card_21: Decimal = Decimal("0")
    card_4: Decimal = Decimal("0")
    cash_21: Decimal = Decimal("0")
    cash_4: Decimal = Decimal("0")
    bizum_21: Decimal = Decimal("0")
    bizum_4: Decimal = Decimal("0")
    cultural_voucher: Decimal = Decimal("0")


class AccountingAccountOut(BaseModel):
    id: int
    code: str
    name: str
    group: int
    account_type: str
    active: bool

    model_config = {"from_attributes": True}


# --- Fase 3: llibres comptables (Diari, Major, Balanç, Compte de resultats) ---
#
# Derivats de JournalEntry/JournalLine (partida doble, ver
# services/comptabilitat_posting.py) — a diferència de ResultatMensualOut
# (que suma directament OrderItem.price/VentaExterna.sale_price, imports
# AMB IVA inclòs), aquests informes surten del llibre major i per tant
# reflecteixen l'IVA per separat (700 net de 477), com un compte de
# resultats de veritat.


class ApuntManualIn(BaseModel):
    compte_code: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    description: str | None = None


class AssentamentManualIn(BaseModel):
    date: date
    description: str
    apunts: list[ApuntManualIn]


class ApuntLlibreOut(BaseModel):
    id: uuid.UUID
    compte_code: str
    compte_name: str
    debit: Decimal
    credit: Decimal
    description: str | None = None


class AssentamentLlibreOut(BaseModel):
    id: uuid.UUID
    entry_number: int
    date: date
    description: str
    source_type: str
    apunts: list[ApuntLlibreOut]


class LlibreDiariOut(BaseModel):
    year: int
    mes: int
    assentaments: list[AssentamentLlibreOut]


class LlibreMajorLiniaOut(BaseModel):
    date: date
    entry_number: int
    description: str
    debit: Decimal
    credit: Decimal
    saldo_acumulat: Decimal


class LlibreMajorOut(BaseModel):
    compte_code: str
    compte_name: str
    year: int
    linies: list[LlibreMajorLiniaOut]
    saldo_final: Decimal


class BalancLiniaOut(BaseModel):
    compte_code: str
    compte_name: str
    saldo: Decimal


class BalancSituacioOut(BaseModel):
    year: int
    mes: int
    actiu: list[BalancLiniaOut]
    passiu: list[BalancLiniaOut]
    patrimoni_net: list[BalancLiniaOut]
    total_actiu: Decimal
    total_passiu_patrimoni_net: Decimal
    quadrat: bool


class ComptePyGLiniaOut(BaseModel):
    compte_code: str
    compte_name: str
    total: Decimal


class ComptePyGOut(BaseModel):
    year: int
    mes: int
    ingressos: list[ComptePyGLiniaOut]
    despeses: list[ComptePyGLiniaOut]
    total_ingressos: Decimal
    total_despeses: Decimal
    resultat: Decimal


# --- Subscripcions (club del disc) ---
#
# No hi ha "plans": el client configura la seva pròpia subscripció
# (periodicitat, quantitat, seccions) dins dels valors que ofereix
# `ConfiguracioSubscripcio` (un sol recurs, com `ConfiguracioBotiga`).

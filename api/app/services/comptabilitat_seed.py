"""Sembra el pla de comptes (`AccountingAccount`) d'un tenant nou segons la
seva jurisdicció comptable i forma jurídica — ver
app/accounting_registry.py per què hi ha un únic proveïdor real (`es`) i la
resta de jurisdiccions són només registre, sense pla implementat.

Cridat des de `routers/superadmin.py::create_tenant`, mateix punt on avui es
sembren `TipusIva`/`TramEnviament`, dins del `with scoped_to(db, tenant.id)`.
"""

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from ..models import AccountingAccount, AccountType


@dataclass(frozen=True)
class AccountSeed:
    code: str
    name: str
    group: int
    account_type: AccountType


def seed_pgc_es(legal_form: str) -> list[AccountSeed]:
    """Pla General Comptable (PYMES) abreujat: els comptes que necessita
    aquest negoci per operar (vendes, compres, IVA, tresoreria, despeses
    habituals) — no el PGC sencer. El grup 1 varia segons forma jurídica:
    una SL porta capital social/reserves (100/112); un autònom en
    comptabilitat completa fa servir el compte del titular (550) en comptes
    de capital social, que no li aplica."""

    grup1: list[AccountSeed] = (
        [
            AccountSeed("100", "Capital social", 1, AccountType.patrimoni_net),
            AccountSeed("112", "Reserva legal", 1, AccountType.patrimoni_net),
        ]
        if legal_form == "sl"
        else [
            AccountSeed("550", "Titular de l'explotació", 1, AccountType.patrimoni_net),
        ]
    )

    return grup1 + [
        AccountSeed("129", "Resultat de l'exercici", 1, AccountType.patrimoni_net),
        AccountSeed("213", "Maquinaria", 2, AccountType.actiu),
        AccountSeed("217", "Equips per a processos d'informació", 2, AccountType.actiu),
        AccountSeed("216", "Mobiliari", 2, AccountType.actiu),
        AccountSeed("218", "Elements de transport", 2, AccountType.actiu),
        AccountSeed("219", "Altres immobilitzats materials", 2, AccountType.actiu),
        AccountSeed("281", "Amortització acumulada de l'immobilitzat material", 2, AccountType.actiu),
        AccountSeed("300", "Mercaderies", 3, AccountType.actiu),
        AccountSeed("400", "Proveïdors", 4, AccountType.passiu),
        AccountSeed("410", "Creditors per prestació de serveis", 4, AccountType.passiu),
        AccountSeed("430", "Clients", 4, AccountType.actiu),
        AccountSeed("472", "H.P. IVA suportat", 4, AccountType.actiu),
        AccountSeed("477", "H.P. IVA repercutit", 4, AccountType.passiu),
        AccountSeed("4750", "H.P. creditora per IVA", 4, AccountType.passiu),
        AccountSeed("570", "Caixa", 5, AccountType.actiu),
        AccountSeed("572", "Bancs", 5, AccountType.actiu),
        AccountSeed("600", "Compres de mercaderies", 6, AccountType.despesa),
        AccountSeed("610", "Variació d'existències de mercaderies", 6, AccountType.despesa),
        AccountSeed("671", "Pèrdues procedents de l'immobilitzat material", 6, AccountType.despesa),
        AccountSeed("621", "Arrendaments", 6, AccountType.despesa),
        AccountSeed("622", "Reparacions i conservació", 6, AccountType.despesa),
        AccountSeed("623", "Serveis de professionals independents", 6, AccountType.despesa),
        AccountSeed("624", "Transports", 6, AccountType.despesa),
        AccountSeed("627", "Publicitat, propaganda i relacions públiques", 6, AccountType.despesa),
        AccountSeed("628", "Subministraments", 6, AccountType.despesa),
        AccountSeed("629", "Altres serveis", 6, AccountType.despesa),
        AccountSeed("681", "Amortització de l'immobilitzat material", 6, AccountType.despesa),
        AccountSeed("700", "Vendes de mercaderies", 7, AccountType.ingres),
        AccountSeed("708", "Devolucions de vendes", 7, AccountType.ingres),
        AccountSeed("771", "Beneficis procedents de l'immobilitzat material", 7, AccountType.ingres),
    ]


# Únic proveïdor real avui — ver accounting_registry.ACCOUNTING_JURISDICTIONS_IMPLEMENTED.
CHART_PROVIDERS: dict[str, Callable[[str], list[AccountSeed]]] = {
    "es": seed_pgc_es,
}

# CategoriaDespesa (comptabilitat.py) -> codi de compte on es posteja la
# despesa (fase 2, motor de posting). Viu aquí i no al model perquè és
# coneixement d'una jurisdicció concreta (el pla de comptes francès/italià
# tindrà el seu propi mapeig quan existeixi el seu chart provider).
#
# "compres_material" -> 300 (Mercaderies), NO 600 (Compres): amb inventari
# permanent (confirmat amb l'usuari) la compra entra directa a l'actiu, i
# el cost surt cap a 610 en el moment de la venda (ver
# comptabilitat_posting.py::post_venda) — 600 es sembra al pla de comptes
# igualment (per si algú l'usa a mà), però el motor de posting automàtic
# mai hi posteja.
DESPESA_CATEGORY_ACCOUNT_ES: dict[str, str] = {
    "compres_material": "300",
    "subministraments": "628",
    "lloguer": "621",
    "comunicacions": "629",
    "serveis_professionals": "623",
    "transport": "624",
    "material_oficina": "629",
    "publicitat": "627",
    "altres": "629",
}


# AssetCategory (models/actius.py) -> codi de compte d'immobilitzat on es
# posteja l'alta de l'actiu (ver comptabilitat_posting.py::post_actiu_alta).
ASSET_CATEGORY_ACCOUNT_ES: dict[str, str] = {
    "maquinaria": "213",
    "mobiliari": "216",
    "equips_informatics": "217",
    "elements_transport": "218",
    "altres": "219",
}


def seed_chart_of_accounts(db: Session, jurisdiction_id: str, legal_form: str) -> None:
    """Crida dins d'un `with scoped_to(db, tenant.id):` (ver app/tenancy.py)
    — `tenant_id` s'omple sol via l'autofill de la sessió, mateix patró que
    ja fan servir els seeds de `TipusIva`/`TramEnviament` a create_tenant."""
    provider = CHART_PROVIDERS.get(jurisdiction_id)
    if provider is None:
        raise ValueError(
            f"Jurisdicció comptable '{jurisdiction_id}' sense pla de comptes implementat "
            "(ver accounting_registry.ACCOUNTING_JURISDICTIONS_IMPLEMENTED)"
        )
    for seed in provider(legal_form):
        db.add(AccountingAccount(code=seed.code, name=seed.name, group=seed.group, account_type=seed.account_type))

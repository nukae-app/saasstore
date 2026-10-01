"""Càlcul de cost real i marge d'una entrada de stock.

El preu de compra s'introdueix SENSE IVA. Per a mercaderia nova comprada a
proveïdor (règim de recàrrec d'equivalència) s'hi afegeix el recàrrec, que no
és recuperable i per tant forma part del cost real sobre el qual es calcula el
marge. El percentatge és `ConfiguracioBotiga.recarrec_equivalencia_pct`
(editable des de l'admin). La segona mà comprada a particulars no porta recàrrec.

La mateixa fórmula es duplica a `web/app/admin/compras/comandes/page.jsx`
(`desglossPreu`) per suggerir el PVP en pantalla: si canvia aquí, canvia allà.
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CondicionItem, ConfiguracioBotiga, TipusIva

RECARREC_PER_DEFECTE_PCT = Decimal("5")
_CENT = Decimal("0.01")


def recarrec_config_pct(db: Session) -> Decimal:
    valor = db.scalar(select(ConfiguracioBotiga.recarrec_equivalencia_pct))
    return RECARREC_PER_DEFECTE_PCT if valor is None else valor


def recarrec_pct(condition: CondicionItem | str, config_pct: Decimal) -> Decimal:
    value = condition.value if isinstance(condition, CondicionItem) else condition
    return config_pct if value == CondicionItem.nou.value else Decimal("0")


def cost_amb_recarrec(cost: Decimal, condition: CondicionItem | str, config_pct: Decimal) -> Decimal:
    return (cost * (1 + recarrec_pct(condition, config_pct) / 100)).quantize(_CENT, ROUND_HALF_UP)


def iva_defecte_pct(db: Session, condition: CondicionItem | str) -> Decimal | None:
    value = condition.value if isinstance(condition, CondicionItem) else condition
    col = TipusIva.default_new if value == CondicionItem.nou.value else TipusIva.default_used
    return db.scalar(select(TipusIva.percentage).where(col.is_(True), TipusIva.active.is_(True)))


def marge_pct(
    price: Decimal, cost: Decimal | None, condition: CondicionItem | str,
    iva_pct: Decimal | None, config_pct: Decimal,
) -> Decimal | None:
    """Marge sobre el cost real: (PVP sense IVA / cost amb recàrrec) - 1.
    None si no hi ha cost o tipus d'IVA per defecte amb què treure la base."""
    if not cost or iva_pct is None:
        return None
    base = price / (1 + iva_pct / 100)
    return ((base / cost_amb_recarrec(cost, condition, config_pct) - 1) * 100).quantize(_CENT, ROUND_HALF_UP)

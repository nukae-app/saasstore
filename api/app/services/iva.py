"""Resolució de l'IVA aplicable a una venda.

Només hi ha dos tipus de producte: disc nou (règim general, IVA sobre el
preu) i disc de 2a mà (REBU si l'ítem ho marca, IVA sobre el marge venda -
cost d'adquisició). El tipus concret a aplicar es configura a l'admin
(`TipusIva.per_defecte_nou` / `per_defecte_segona_ma`) i es desa com a
snapshot a la venda (igual que el preu), perquè un canvi de tipus més
endavant no alteri vendes passades.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CondicionItem, Item, TipusIva


def resolve_tipus_iva_venda(item: Item, db: Session) -> TipusIva | None:
    """Tipus d'IVA configurat per defecte per a aquest ítem (nou o segona mà/REBU)."""
    campo = TipusIva.default_used if item.condition == CondicionItem.segona_ma else TipusIva.default_new
    return db.scalar(select(TipusIva).where(campo == True, TipusIva.active == True))


def compute_iva_venda(item: Item, precio_venta: Decimal, db: Session) -> tuple[int | None, Decimal | None, Decimal | None]:
    """Calcula (tipus_iva_id, iva_pct, iva_import) per a una venda d'`item` a `precio_venta`.

    Si l'ítem és REBU, l'IVA es calcula sobre el marge (preu - cost); si no
    hi ha cost registrat, no es pot determinar el marge i es retorna sense
    IVA calculat (cal completar-ho a mà des de comptabilitat).
    Si no hi ha cap tipus configurat per defecte, no es calcula res (mateix cas).
    """
    tipus = resolve_tipus_iva_venda(item, db)
    if tipus is None:
        return None, None, None

    if tipus.is_rebu:
        if item.acquisition_cost is None:
            return tipus.id, tipus.percentage, None
        base_calculo = precio_venta - item.acquisition_cost
    else:
        base_calculo = precio_venta

    if base_calculo <= 0:
        return tipus.id, tipus.percentage, Decimal("0.00")

    pct = tipus.percentage
    iva_import = (base_calculo * pct / (Decimal("100") + pct)).quantize(Decimal("0.01"))
    return tipus.id, pct, iva_import

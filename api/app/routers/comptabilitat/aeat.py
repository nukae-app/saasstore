"""Caselles del Model 303 (IVA trimestral), règim general — NO genera cap
fitxer oficial de presentació (ver docstring del mòdul de contabilitat per
context: no es va poder verificar el disseny de registre oficial des
d'aquest entorn). Números per copiar a mà a la seu electrònica o passar a
la gestoria.

Fora d'abast deliberat: intracomunitàries, importacions, prorrata,
compensació de quotes d'exercicis anteriors — ver Model303Out.fora_abast."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Despesa, FixedAsset, Item, Order, OrderItem, OrderStatus, VentaExterna
from ...schemas import Model303Out, Model303TipusOut
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])

TRAMS_OFICIALS = {Decimal("21.00"): "general", Decimal("10.00"): "reduit", Decimal("4.00"): "superreduit"}


@router.get("/aeat/303/{year}/{trimestre}", response_model=Model303Out)
def model_303(year: int, trimestre: int, db: Session = Depends(get_db)):
    if not (1 <= trimestre <= 4):
        raise HTTPException(422, "Trimestre ha de ser entre 1 i 4")
    mesos = [(trimestre - 1) * 3 + i for i in range(1, 4)]

    def _in_trimestre(col):
        return (extract("year", col) == year) & (extract("month", col).in_(mesos))

    # --- IVA repercutit (01-09/27) — mateixa font que iva_trimestral existent ---
    web_rows = db.execute(
        select(OrderItem.vat_pct, OrderItem.price, OrderItem.quantity, OrderItem.vat_amount)
        .join(Order, Order.id == OrderItem.order_id)
        .where(_in_trimestre(Order.created_at))
        .where(Order.status.in_([OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado]))
    ).all()
    ve_rows = db.execute(
        select(VentaExterna.vat_pct, VentaExterna.sale_price, VentaExterna.vat_amount)
        .where(_in_trimestre(VentaExterna.date))
    ).all()

    trams: dict[Decimal, list[Decimal]] = {}

    def _acumula(pct: Decimal | None, preu_total: Decimal, iva_import: Decimal | None) -> None:
        pct_efectiu = pct if pct is not None else Decimal("21.00")
        if iva_import is None:
            iva_import = (preu_total * pct_efectiu / (Decimal("100") + pct_efectiu)).quantize(Decimal("0.01"))
        acc = trams.setdefault(pct_efectiu, [Decimal("0"), Decimal("0")])
        acc[0] += preu_total - iva_import
        acc[1] += iva_import

    for pct, price, quantity, vat_amount in web_rows:
        _acumula(pct, price * quantity, vat_amount)
    for pct, sale_price, vat_amount in ve_rows:
        _acumula(pct, sale_price, vat_amount)

    def _tram(pct: Decimal) -> Model303TipusOut | None:
        vals = trams.get(pct)
        return Model303TipusOut(pct=pct, base=vals[0], cuota=vals[1]) if vals else None

    altres = [
        Model303TipusOut(pct=pct, base=vals[0], cuota=vals[1])
        for pct, vals in trams.items() if pct not in TRAMS_OFICIALS
    ]
    casella_27 = sum((v[1] for k, v in trams.items()), Decimal("0"))

    # --- IVA suportat corrent (28/29) — totes les Despesa, mai un actiu ---
    corrent = db.execute(
        select(Despesa.taxable_base, Despesa.vat_amount).where(_in_trimestre(Despesa.invoice_date))
    ).all()
    casella_28 = sum((r[0] for r in corrent), Decimal("0"))
    casella_29 = sum((r[1] or Decimal("0") for r in corrent), Decimal("0"))

    # --- IVA suportat béns d'inversió (30/31) — actius fixos donats d'alta al trimestre ---
    inversio = db.execute(
        select(FixedAsset.acquisition_cost, FixedAsset.vat_amount).where(_in_trimestre(FixedAsset.acquisition_date))
    ).all()
    casella_30 = sum((r[0] for r in inversio), Decimal("0"))
    casella_31 = sum((r[1] or Decimal("0") for r in inversio), Decimal("0"))

    casella_45 = casella_29 + casella_31
    casella_46 = casella_27 - casella_45

    hay_rebu = db.execute(
        select(VentaExterna)
        .join(Item, Item.id == VentaExterna.item_id)
        .where(_in_trimestre(VentaExterna.date))
        .where(Item.rebu == True)
        .limit(1)
    ).first() is not None

    return Model303Out(
        year=year, trimestre=trimestre, mesos=mesos,
        repercutit_general=_tram(Decimal("21.00")), repercutit_reduit=_tram(Decimal("10.00")),
        repercutit_superreduit=_tram(Decimal("4.00")), altres_tipus_repercutit=altres,
        casella_27_cuota_meritada=casella_27,
        casella_28_base_corrent=casella_28, casella_29_cuota_corrent=casella_29,
        casella_30_base_inversio=casella_30, casella_31_cuota_inversio=casella_31,
        casella_45_total_a_deduir=casella_45,
        casella_46_resultat_regim_general=casella_46, casella_64_resultat_liquidacio=casella_46,
        nota_rebu=hay_rebu,
    )

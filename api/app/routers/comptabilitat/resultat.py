from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import (
    CanalVenta, Despesa, Item, ItemStatus, Order, OrderItem, OrderStatus, PeriodeComptable,
    VentaExterna,
)
from ...schemas import IVALiniaOut, IVATrimestralOut, ResultatLiniaDespesa, ResultatMensualOut
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


@router.get("/resultat/{year}/{mes}", response_model=ResultatMensualOut)
def resultat_mensual(year: int, mes: int, db: Session = Depends(get_db)):
    if not (1 <= mes <= 12):
        raise HTTPException(422, "Mes ha de ser entre 1 i 12")

    # Periode
    periode = db.scalar(
        select(PeriodeComptable).where(PeriodeComptable.year == year, PeriodeComptable.month == mes)
    )
    tancat = periode.closed if periode else False

    def _mes_filter(col):
        return (extract("year", col) == year) & (extract("month", col) == mes)

    # Vendes web (orders pagades/enviades/entregades)
    vendes_web_rows = db.execute(
        select(func.sum(OrderItem.price))
        .join(Order, Order.id == OrderItem.order_id)
        .where(_mes_filter(Order.created_at))
        .where(Order.status.in_([OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado]))
    ).scalar() or Decimal("0")

    # Vendes TPV mostrador
    vendes_mostrador = db.execute(
        select(func.sum(VentaExterna.sale_price))
        .where(_mes_filter(VentaExterna.date))
        .where(VentaExterna.channel == CanalVenta.mostrador)
    ).scalar() or Decimal("0")

    # Vendes Discogs
    vendes_discogs = db.execute(
        select(func.sum(VentaExterna.sale_price))
        .where(_mes_filter(VentaExterna.date))
        .where(VentaExterna.channel == CanalVenta.discogs)
    ).scalar() or Decimal("0")

    total_ingressos = vendes_web_rows + vendes_mostrador + vendes_discogs

    # COGS web: cost dels items venuts via web aquell mes
    cogs_web_row = db.execute(
        select(
            # coste_adquisicion es por unidad: para nou, una OrderItem puede
            # vender más de 1 unidad de la misma línea de golpe.
            func.coalesce(func.sum(Item.acquisition_cost * OrderItem.quantity), Decimal("0")),
            func.count(Item.id).filter(Item.acquisition_cost.is_(None)),
        )
        .join(OrderItem, OrderItem.item_id == Item.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(_mes_filter(Order.created_at))
        .where(Order.status.in_([OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado]))
    ).one()
    cogs_web = cogs_web_row[0] or Decimal("0")
    sense_cost_web = cogs_web_row[1] or 0

    # COGS extern: cost dels items venuts via TPV/Discogs aquell mes
    cogs_extern_row = db.execute(
        select(
            func.coalesce(func.sum(Item.acquisition_cost * VentaExterna.quantity), Decimal("0")),
            func.count(Item.id).filter(Item.acquisition_cost.is_(None)),
        )
        .join(VentaExterna, VentaExterna.item_id == Item.id)
        .where(_mes_filter(VentaExterna.date))
    ).one()
    cogs_extern = cogs_extern_row[0] or Decimal("0")
    sense_cost_extern = cogs_extern_row[1] or 0

    total_cogs = cogs_web + cogs_extern
    items_sense_cost = sense_cost_web + sense_cost_extern
    marge_brut = total_ingressos - total_cogs

    # Despeses del mes per categoria (totes, per compatibilitat i IVA)
    despeses_rows = db.execute(
        select(Despesa.category, func.sum(Despesa.total), func.count(Despesa.id))
        .where(_mes_filter(Despesa.invoice_date))
        .group_by(Despesa.category)
        .order_by(Despesa.category)
    ).all()

    despeses_out = [
        ResultatLiniaDespesa(categoria=r[0], total=r[1], num_factures=r[2])
        for r in despeses_rows
    ]
    total_despeses = sum(d.total for d in despeses_out)

    # Despeses operatives: exclou compres_material (ja reflectit al COGS per-venda)
    total_despeses_operatives = sum(
        d.total for d in despeses_out if d.categoria != "compres_material"
    )

    return ResultatMensualOut(
        year=year,
        mes=mes,
        periode_tancat=tancat,
        vendes_web=Decimal(vendes_web_rows),
        vendes_mostrador=Decimal(vendes_mostrador),
        vendes_discogs=Decimal(vendes_discogs),
        total_ingressos=total_ingressos,
        cogs_web=cogs_web,
        cogs_extern=cogs_extern,
        total_cogs=total_cogs,
        items_sense_cost=items_sense_cost,
        marge_brut=marge_brut,
        despeses=despeses_out,
        total_despeses_operatives=total_despeses_operatives,
        total_despeses=total_despeses,
        resultat=marge_brut - total_despeses_operatives,
    )


@router.get("/iva/{year}/{trimestre}", response_model=IVATrimestralOut)
def iva_trimestral(year: int, trimestre: int, db: Session = Depends(get_db)):
    if not (1 <= trimestre <= 4):
        raise HTTPException(422, "Trimestre ha de ser entre 1 i 4")

    mesos = [(trimestre - 1) * 3 + i for i in range(1, 4)]  # [1,2,3], [4,5,6]...

    def _in_trimestre(col):
        return (extract("year", col) == year) & (extract("month", col).in_(mesos))

    # IVA suportat (despeses)
    suportat_rows = db.execute(
        select(Despesa.category, Despesa.vat_pct, func.sum(Despesa.taxable_base), func.sum(Despesa.vat_amount))
        .where(_in_trimestre(Despesa.invoice_date))
        .group_by(Despesa.category, Despesa.vat_pct)
        .order_by(Despesa.category)
    ).all()

    iva_suportat = [
        IVALiniaOut(categoria=r[0], iva_pct=r[1], base=r[2], iva_import=r[3])
        for r in suportat_rows
    ]

    # IVA repercutit (vendes). Cada línia ja porta el seu iva_pct/iva_import desat
    # en el moment de la venda (règim general sobre preu, o REBU sobre el marge).
    # Per a vendes anteriors a aquesta funcionalitat (iva_import NULL) s'assumeix
    # el tipus general (21%) sobre el preu, igual que feia l'informe abans.
    web_rows = db.execute(
        select(OrderItem.vat_pct, OrderItem.price, OrderItem.vat_amount)
        .join(Order, Order.id == OrderItem.order_id)
        .where(_in_trimestre(Order.created_at))
        .where(Order.status.in_([OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado]))
    ).all()

    canal_labels = {"mostrador": "vendes_mostrador", "discogs": "vendes_discogs", "otro": "vendes_altres"}
    ve_rows = db.execute(
        select(VentaExterna.channel, VentaExterna.vat_pct, VentaExterna.sale_price, VentaExterna.vat_amount)
        .where(_in_trimestre(VentaExterna.date))
    ).all()

    hay_rebu = db.execute(
        select(func.count())
        .select_from(VentaExterna)
        .join(Item, Item.id == VentaExterna.item_id)
        .where(_in_trimestre(VentaExterna.date))
        .where(Item.rebu == True)
    ).scalar() > 0

    def _agregar(label_pct_precio_iva: list[tuple[str, Decimal | None, Decimal, Decimal | None]]) -> list[IVALiniaOut]:
        buckets: dict[tuple[str, Decimal], list[Decimal]] = {}
        for label, pct, precio, iva_import in label_pct_precio_iva:
            pct_efectiu = pct if pct is not None else Decimal("21.00")
            if iva_import is None:
                iva_import = (precio * pct_efectiu / (Decimal("100") + pct_efectiu)).quantize(Decimal("0.01"))
            key = (label, pct_efectiu)
            acc = buckets.setdefault(key, [Decimal("0"), Decimal("0")])
            acc[0] += precio - iva_import
            acc[1] += iva_import
        return [
            IVALiniaOut(categoria=k[0], iva_pct=k[1], base=v[0], iva_import=v[1])
            for k, v in buckets.items()
        ]

    repercutit_rows = [("vendes_web", pct, precio, iva) for pct, precio, iva in web_rows]
    repercutit_rows += [
        (canal_labels.get(canal, canal), pct, precio, iva) for canal, pct, precio, iva in ve_rows
    ]
    iva_repercutit = _agregar(repercutit_rows)

    total_base_suportat = sum(r.base for r in iva_suportat)
    total_iva_suportat = sum(r.iva_import for r in iva_suportat)
    total_base_repercutit = sum(r.base for r in iva_repercutit)
    total_iva_repercutit = sum(r.iva_import for r in iva_repercutit)

    return IVATrimestralOut(
        year=year,
        trimestre=trimestre,
        mesos=mesos,
        iva_suportat=iva_suportat,
        total_base_suportat=total_base_suportat,
        total_iva_suportat=total_iva_suportat,
        iva_repercutit=iva_repercutit,
        total_base_repercutit=total_base_repercutit,
        total_iva_repercutit=total_iva_repercutit,
        resultat_iva=total_iva_repercutit - total_iva_suportat,
        nota_rebu=hay_rebu,
    )


@router.get("/stock/valor")
def stock_valor(db: Session = Depends(get_db)):
    """Valor actual de l'estoc a preu de cost, desglossat per estat i condició."""
    rows = db.execute(
        select(
            Item.status,
            Item.condition,
            # Para nou, una fila representa `cantidad` unidades físicas: hay
            # que ponderar por cantidad para reflejar el valor real de estoc,
            # no el de una sola unidad por línea.
            func.coalesce(func.sum(Item.quantity), 0).label("num_items"),
            func.coalesce(func.sum(Item.acquisition_cost * Item.quantity), Decimal("0")).label("valor_cost"),
            func.coalesce(func.sum(Item.price * Item.quantity), Decimal("0")).label("valor_pvp"),
            func.count(Item.id).filter(Item.acquisition_cost.is_(None)).label("sense_cost"),
        )
        .where(Item.status.in_([ItemStatus.disponible, ItemStatus.reservado]))
        .group_by(Item.status, Item.condition)
        .order_by(Item.status, Item.condition)
    ).all()

    total_items = sum(r.num_items for r in rows)
    total_valor_cost = sum(r.valor_cost for r in rows)
    total_valor_pvp = sum(r.valor_pvp for r in rows)
    total_sense_cost = sum(r.sense_cost for r in rows)

    return {
        "total_items": total_items,
        "total_valor_cost": total_valor_cost,
        "total_valor_pvp": total_valor_pvp,
        "marge_potencial": total_valor_pvp - total_valor_cost,
        "items_sense_cost": total_sense_cost,
        "detall": [
            {
                "status": r.status,
                "condicion": r.condition,
                "num_items": r.num_items,
                "valor_cost": r.valor_cost,
                "valor_pvp": r.valor_pvp,
                "sense_cost": r.sense_cost,
            }
            for r in rows
        ],
    }

import calendar
import io
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import CaixaDiaria, CanalVenta, MetodoPago, Order, OrderItem, OrderStatus, PeriodeComptable, VentaExterna
from ...schemas import (
    CAIXA_DIARIA_CAMPS, CaixaDiariaLiniaIn, CaixaDiariaLiniaOut, CaixaDiariaMesOut, VendesRealsLiniaOut,
)
from ...services.caixa_diaria_export import generate_caixa_diaria_excel, generate_caixa_diaria_pdf
from ...services.comptabilitat_posting import post_caixa_diaria
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


def _validar_mes(mes: int):
    if not (1 <= mes <= 12):
        raise HTTPException(422, "Mes ha de ser entre 1 i 12")


def _dies_del_mes(year: int, mes: int) -> list[date]:
    n = calendar.monthrange(year, mes)[1]
    return [date(year, mes, d) for d in range(1, n + 1)]


def _linia_out(data_: date, caixa: CaixaDiaria | None) -> CaixaDiariaLiniaOut:
    valors = {camp: getattr(caixa, camp) if caixa else Decimal("0") for camp in CAIXA_DIARIA_CAMPS}
    return CaixaDiariaLiniaOut(date=data_, total_dia=sum(valors.values()), **valors)


def _get_caixa_diaria_mes(year: int, mes: int, db: Session) -> CaixaDiariaMesOut:
    periode = db.scalar(
        select(PeriodeComptable).where(PeriodeComptable.year == year, PeriodeComptable.month == mes)
    )
    dies = _dies_del_mes(year, mes)
    existents = {c.date: c for c in db.scalars(select(CaixaDiaria).where(CaixaDiaria.date.in_(dies)))}
    linies = [_linia_out(d, existents.get(d)) for d in dies]

    totals = {camp: sum(getattr(l, camp) for l in linies) for camp in CAIXA_DIARIA_CAMPS}
    total_mes = sum(totals.values())

    return CaixaDiariaMesOut(
        year=year, mes=mes,
        periode_tancat=periode.closed if periode else False,
        dies=linies,
        totals=CaixaDiariaLiniaOut(date=dies[0], total_dia=total_mes, **totals),
        total_mes=total_mes,
    )


@router.get("/caixa-diaria/{year}/{mes}", response_model=CaixaDiariaMesOut)
def get_caixa_diaria(year: int, mes: int, db: Session = Depends(get_db)):
    _validar_mes(mes)
    return _get_caixa_diaria_mes(year, mes, db)


def _camp_iva(prefix: str, iva_pct) -> str | None:
    if iva_pct == 21:
        return f"{prefix}_21"
    if iva_pct == 4:
        return f"{prefix}_4"
    return None  # tipus d'IVA configurat fora de 21%/4% — no hi encaixa a la graella


_PREFIX_PER_METODE = {
    MetodoPago.tarjeta: "card",
    MetodoPago.efectivo: "cash",
    MetodoPago.bizum: "bizum",
    # cultural_voucher no es desglossa per IVA: una sola columna a la graella.
}


@router.get("/caixa-diaria/{year}/{mes}/vendes-reals", response_model=list[VendesRealsLiniaOut])
def get_vendes_reals(year: int, mes: int, db: Session = Depends(get_db)):
    """Reconstrueix targeta/efectiu/bizum/bono cultural per dia a partir de
    vendes reals, perquè l'admin no hagi de teclejar-les: vendes web pagades
    amb Redsys (sempre targeta) i vendes de mostrador (TPV, `VentaExterna.canal
    == mostrador`) amb el mètode de pagament que es va triar al cobrar. Deixa
    fora Discogs (cobrament fora de la nostra caixa) i les comandes web 'paga
    en recollir' (un cop cobrades a mostrador no queda registrat si van pagar
    en efectiu o targeta) — aquests casos, com paypal/transferència, s'ajusten
    a mà."""
    _validar_mes(mes)

    def _mes_filter(col):
        return (extract("year", col) == year) & (extract("month", col) == mes)

    acumulat: dict[date, dict[str, Decimal]] = {}

    def _afegeix(dia: date, camp: str, import_: Decimal):
        fila = acumulat.setdefault(dia, {
            "card_21": Decimal("0"), "card_4": Decimal("0"),
            "cash_21": Decimal("0"), "cash_4": Decimal("0"),
            "bizum_21": Decimal("0"), "bizum_4": Decimal("0"),
            "cultural_voucher": Decimal("0"),
        })
        fila[camp] += import_

    web_rows = db.execute(
        select(func.date(Order.created_at), OrderItem.vat_pct, func.sum(OrderItem.price))
        .join(Order, Order.id == OrderItem.order_id)
        .where(_mes_filter(Order.created_at))
        .where(Order.status.in_([OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado]))
        .where(Order.payment_method == "redsys")
        .group_by(func.date(Order.created_at), OrderItem.vat_pct)
    ).all()
    for dia, iva_pct, total in web_rows:
        camp = _camp_iva("card", iva_pct)
        if camp and total:
            _afegeix(dia, camp, total)

    tpv_rows = db.execute(
        select(func.date(VentaExterna.date), VentaExterna.payment_method, VentaExterna.vat_pct,
               func.sum(VentaExterna.sale_price))
        .where(_mes_filter(VentaExterna.date))
        .where(VentaExterna.channel == CanalVenta.mostrador)
        .group_by(func.date(VentaExterna.date), VentaExterna.payment_method, VentaExterna.vat_pct)
    ).all()
    for dia, metode, iva_pct, total in tpv_rows:
        if not total:
            continue
        if metode == MetodoPago.bono_cultural:
            _afegeix(dia, "cultural_voucher", total)
            continue
        prefix = _PREFIX_PER_METODE.get(metode)
        camp = _camp_iva(prefix, iva_pct) if prefix else None
        if camp:
            _afegeix(dia, camp, total)

    return [
        VendesRealsLiniaOut(date=dia, **valors)
        for dia, valors in sorted(acumulat.items())
    ]


@router.put("/caixa-diaria/{year}/{mes}", response_model=CaixaDiariaMesOut)
def save_caixa_diaria(year: int, mes: int, payload: list[CaixaDiariaLiniaIn], db: Session = Depends(get_db)):
    _validar_mes(mes)
    periode = db.scalar(
        select(PeriodeComptable).where(PeriodeComptable.year == year, PeriodeComptable.month == mes)
    )
    if periode and periode.closed:
        raise HTTPException(409, "El mes està tancat — obre'l primer per editar la caixa")

    dies_valids = set(_dies_del_mes(year, mes))
    existents = {c.date: c for c in db.scalars(select(CaixaDiaria).where(CaixaDiaria.date.in_(dies_valids)))}
    for linia in payload:
        if linia.date not in dies_valids:
            raise HTTPException(422, f"{linia.date} no pertany a {mes}/{year}")
        caixa = existents.get(linia.date)
        if caixa is None:
            caixa = CaixaDiaria(date=linia.date)
            db.add(caixa)
            existents[linia.date] = caixa
        for camp in CAIXA_DIARIA_CAMPS:
            setattr(caixa, camp, getattr(linia, camp))
        db.flush()
        post_caixa_diaria(db, caixa)
    db.commit()

    return _get_caixa_diaria_mes(year, mes, db)


@router.get("/caixa-diaria/{year}/{mes}/excel")
def export_caixa_diaria_excel(year: int, mes: int, db: Session = Depends(get_db)):
    _validar_mes(mes)
    mes_data = _get_caixa_diaria_mes(year, mes, db)
    xlsx_bytes = generate_caixa_diaria_excel(mes_data)
    filename = f"caixa_{year}_{mes:02d}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/caixa-diaria/{year}/{mes}/pdf")
def export_caixa_diaria_pdf(year: int, mes: int, db: Session = Depends(get_db)):
    _validar_mes(mes)
    mes_data = _get_caixa_diaria_mes(year, mes, db)
    pdf_bytes = generate_caixa_diaria_pdf(mes_data)
    filename = f"caixa_{year}_{mes:02d}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

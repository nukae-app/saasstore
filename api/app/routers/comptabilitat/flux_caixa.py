"""Flux de caixa projectat (docs/PLAN_PARIDAD_HOLDED.md B3): a diferència de
la caixa diaria (històrica), això és una projecció a futur que combina
`Despesa.due_date` pendents amb l'estacionalitat de vendes (mitjana
històrica del mateix mes natural en anys anteriors) — no una regressió ni
tendència, deliberadament simple.

Limitació coneguda i acceptada (v1): només compta despeses ja facturades
amb `due_date` — una despesa recurrent futura (lloguer del mes vinent) que
encara no s'ha donat d'alta com a `Despesa` no apareix a la projecció."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import (
    AccountingAccount, CanalVenta, Despesa, EstatPagamentDespesa, JournalLine,
    Order, OrderItem, OrderStatus, VentaExterna,
)
from ...schemas import FluxCaixaLiniaOut, FluxCaixaProjectatOut
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])

GRUP_TRESORERIA = 5  # 570 Caixa, 572 Bancs (services/comptabilitat_seed.py)


def _saldo_tresoreria_actual(db: Session) -> Decimal:
    return db.execute(
        select(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), Decimal("0.00")))
        .join(AccountingAccount, AccountingAccount.id == JournalLine.account_id)
        .where(AccountingAccount.group == GRUP_TRESORERIA)
    ).scalar() or Decimal("0.00")


def _ingressos_bruts_mes(db: Session, any_: int, mes: int) -> Decimal:
    """Mateixa base (bruta, IVA inclòs) que `resultat.py::resultat_mensual` —
    la que correspon a una projecció de caixa, a diferència del compte de
    resultats net d'IVA del llibre major."""
    def _mes_filter(col):
        return (extract("year", col) == any_) & (extract("month", col) == mes)

    vendes_web = db.execute(
        select(func.sum(OrderItem.price))
        .join(Order, Order.id == OrderItem.order_id)
        .where(_mes_filter(Order.created_at))
        .where(Order.status.in_([OrderStatus.pagado, OrderStatus.enviado, OrderStatus.entregado]))
    ).scalar() or Decimal("0.00")

    vendes_externes = db.execute(
        select(func.sum(VentaExterna.sale_price))
        .where(_mes_filter(VentaExterna.date))
        .where(VentaExterna.channel.in_([CanalVenta.mostrador, CanalVenta.discogs]))
    ).scalar() or Decimal("0.00")

    return vendes_web + vendes_externes


@router.get("/flux-caixa-projectat", response_model=FluxCaixaProjectatOut)
def flux_caixa_projectat(mesos: int = 6, anys_historic: int = 3, db: Session = Depends(get_db)):
    if not (1 <= mesos <= 24):
        raise HTTPException(422, "Mesos ha de ser entre 1 i 24")
    if not (1 <= anys_historic <= 10):
        raise HTTPException(422, "Anys_historic ha de ser entre 1 i 10")

    avui = date.today()
    saldo_actual = _saldo_tresoreria_actual(db)
    saldo = saldo_actual
    linies: list[FluxCaixaLiniaOut] = []

    for i in range(1, mesos + 1):
        total_mesos = avui.month - 1 + i
        any_ = avui.year + total_mesos // 12
        mes = total_mesos % 12 + 1

        # Estacionalitat: mitjana d'ingressos bruts d'aquest mes natural en
        # els `anys_historic` anys anteriors — només es divideix pels anys
        # que realment tenen dades, perquè un negoci jove no infravalori la
        # temporada alta pels seus primers anys sense vendes.
        ingressos_per_any = [
            _ingressos_bruts_mes(db, any_ - k, mes) for k in range(1, anys_historic + 1)
        ]
        anys_amb_dades = [v for v in ingressos_per_any if v > 0]
        ingressos_estimats = (sum(anys_amb_dades) / len(anys_amb_dades)) if anys_amb_dades else Decimal("0.00")

        despeses_pendents = db.execute(
            select(func.coalesce(func.sum(Despesa.total), Decimal("0.00")))
            .where(Despesa.payment_status.in_([EstatPagamentDespesa.pendent, EstatPagamentDespesa.vencut]))
            .where(extract("year", Despesa.due_date) == any_)
            .where(extract("month", Despesa.due_date) == mes)
        ).scalar() or Decimal("0.00")

        saldo += ingressos_estimats - despeses_pendents
        linies.append(FluxCaixaLiniaOut(
            year=any_, mes=mes, ingressos_estimats=ingressos_estimats,
            despeses_pendents=despeses_pendents, saldo_projectat=saldo,
        ))

    return FluxCaixaProjectatOut(saldo_actual=saldo_actual, anys_historic=anys_historic, linies=linies)

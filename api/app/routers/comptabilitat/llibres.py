"""Llibres comptables derivats de la partida doble (JournalEntry/JournalLine
— ver services/comptabilitat_posting.py): Diari, Major, Balanç de Situació i
Compte de Pèrdues i Guanys.

A diferència de `resultat.py` (que suma directament OrderItem.price/
VentaExterna.sale_price, imports AMB IVA inclòs — útil per quadrar caixa,
però no és un compte de resultats de veritat), aquests informes surten del
llibre major i per tant l'IVA hi apareix per separat (700 net de 477)."""

import calendar
import csv
import io
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import AccountingAccount, AccountType, JournalEntry, JournalLine
from ...schemas import (
    AccountingAccountOut, ApuntLlibreOut, AssentamentLlibreOut, BalancLiniaOut, BalancSituacioOut,
    ComptePyGLiniaOut, ComptePyGOut, LlibreDiariOut, LlibreMajorLiniaOut, LlibreMajorOut,
)
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


@router.get("/comptes-comptables", response_model=list[AccountingAccountOut])
def list_comptes_comptables(db: Session = Depends(get_db)):
    accounts = db.scalars(select(AccountingAccount).order_by(AccountingAccount.code)).all()
    return [
        AccountingAccountOut(
            id=a.id, code=a.code, name=a.name, group=a.group, account_type=a.account_type.value, active=a.active,
        )
        for a in accounts
    ]


def _validar_mes(mes: int) -> None:
    if not (1 <= mes <= 12):
        raise HTTPException(422, "Mes ha de ser entre 1 i 12")


def _fi_de_mes(year: int, mes: int) -> date:
    return date(year, mes, calendar.monthrange(year, mes)[1])


@router.get("/llibre-diari/{year}/export")
def llibre_diari_export(year: int, mes_desde: int = 1, mes_fins: int = 12, db: Session = Depends(get_db)):
    """CSV genèric (delimitat per punt i coma, decimals amb coma — s'obre
    net a Excel/LibreOffice en configuració espanyola sense assistent
    d'importació): Data, Assentament, Compte, Nom del compte, Concepte,
    Debe, Haver. No assumeix cap software concret de gestoria — qualsevol
    despatx el pot important tal qual o revisar-lo directament."""
    _validar_mes(mes_desde)
    _validar_mes(mes_fins)
    if mes_desde > mes_fins:
        raise HTTPException(422, "mes_desde no pot ser posterior a mes_fins")

    entries = db.scalars(
        select(JournalEntry)
        .where(JournalEntry.fiscal_year == year)
        .where(JournalEntry.date >= date(year, mes_desde, 1), JournalEntry.date <= _fi_de_mes(year, mes_fins))
        .options(selectinload(JournalEntry.lines).selectinload(JournalLine.account))
        .order_by(JournalEntry.entry_number)
    ).all()

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Data", "Assentament", "Compte", "Nom del compte", "Concepte", "Debe", "Haver"])
    for e in entries:
        for l in e.lines:
            writer.writerow([
                e.date.isoformat(), e.entry_number, l.account.code, l.account.name,
                l.description or e.description,
                str(l.debit).replace(".", ","), str(l.credit).replace(".", ","),
            ])

    filename = f"llibre_diari_{year}_{mes_desde:02d}-{mes_fins:02d}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/llibre-diari/{year}/{mes}", response_model=LlibreDiariOut)
def llibre_diari(year: int, mes: int, db: Session = Depends(get_db)):
    _validar_mes(mes)
    entries = db.scalars(
        select(JournalEntry)
        .where(JournalEntry.fiscal_year == year)
        .where(JournalEntry.date >= date(year, mes, 1), JournalEntry.date <= _fi_de_mes(year, mes))
        .options(selectinload(JournalEntry.lines).selectinload(JournalLine.account))
        .order_by(JournalEntry.entry_number)
    ).all()
    return LlibreDiariOut(
        year=year, mes=mes,
        assentaments=[
            AssentamentLlibreOut(
                id=e.id, entry_number=e.entry_number, date=e.date, description=e.description,
                source_type=e.source_type.value,
                apunts=[
                    ApuntLlibreOut(
                        id=l.id, compte_code=l.account.code, compte_name=l.account.name,
                        debit=l.debit, credit=l.credit, description=l.description,
                    )
                    for l in e.lines
                ],
            )
            for e in entries
        ],
    )


@router.get("/llibre-major/{year}", response_model=LlibreMajorOut)
def llibre_major(year: int, compte: str, db: Session = Depends(get_db)):
    """`compte` és el codi PGC (p. ex. "572"), no l'id — més còmode des del
    front, que ja coneix els codis (ver `/comptes-comptables`)."""
    account = db.scalar(select(AccountingAccount).where(AccountingAccount.code == compte))
    if account is None:
        raise HTTPException(404, f"Compte '{compte}' no trobat al pla de comptes")

    lines = db.scalars(
        select(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalLine.account_id == account.id, JournalEntry.fiscal_year == year)
        .options(selectinload(JournalLine.entry))
        .order_by(JournalEntry.date, JournalEntry.entry_number)
    ).all()

    normal_debit = account.account_type in (AccountType.actiu, AccountType.despesa)
    saldo = Decimal("0")
    linies_out: list[LlibreMajorLiniaOut] = []
    for l in lines:
        saldo += (l.debit - l.credit) if normal_debit else (l.credit - l.debit)
        linies_out.append(LlibreMajorLiniaOut(
            date=l.entry.date, entry_number=l.entry.entry_number, description=l.entry.description,
            debit=l.debit, credit=l.credit, saldo_acumulat=saldo,
        ))

    return LlibreMajorOut(compte_code=account.code, compte_name=account.name, year=year, linies=linies_out, saldo_final=saldo)


def _saldos_per_tipus(db: Session, account_types: tuple[AccountType, ...], data_fins: date | None, data_des_de: date | None = None) -> dict[AccountType, list[BalancLiniaOut]]:
    """Suma debit/credit per compte, filtrat per tipus i per data — `data_fins`
    sola (sense `data_des_de`) dona el saldo ACUMULAT fins aquella data
    (balanç de situació: un actiu no es reinicia cada mes); amb totes dues
    dona el moviment NOMÉS d'aquest període (compte de resultats: un
    ingrés/despesa és sempre d'un període concret)."""
    stmt = (
        select(
            AccountingAccount.code, AccountingAccount.name, AccountingAccount.account_type,
            JournalLine.debit, JournalLine.credit,
        )
        .join(JournalLine, JournalLine.account_id == AccountingAccount.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(AccountingAccount.account_type.in_(account_types))
        .where(JournalEntry.date <= data_fins)
    )
    if data_des_de is not None:
        stmt = stmt.where(JournalEntry.date >= data_des_de)
    rows = db.execute(stmt).all()

    acumulat: dict[tuple[str, str, AccountType], Decimal] = {}
    for code, name, tipus, debit, credit in rows:
        key = (code, name, tipus)
        normal_debit = tipus in (AccountType.actiu, AccountType.despesa)
        delta = (debit - credit) if normal_debit else (credit - debit)
        acumulat[key] = acumulat.get(key, Decimal("0")) + delta

    resultat: dict[AccountType, list[BalancLiniaOut]] = {t: [] for t in account_types}
    for (code, name, tipus), saldo in sorted(acumulat.items()):
        if saldo == 0:
            continue
        resultat[tipus].append(BalancLiniaOut(compte_code=code, compte_name=name, saldo=saldo))
    return resultat


@router.get("/balanc-situacio/{year}/{mes}", response_model=BalancSituacioOut)
def balanc_situacio(year: int, mes: int, db: Session = Depends(get_db)):
    """Saldo ACUMULAT de cada compte patrimonial fins al darrer dia del mes
    — no es reinicia cada any (un compte bancari no "torna a zero" a gener),
    a diferència del compte de resultats de sota.

    Inclou una línia sintètica "129 Resultat de l'exercici (provisional)"
    dins de patrimoni net amb l'acumulat ingressos-despeses de l'any fins
    aquest mes: sense això, un balanç intermedi (abans del tancament anual,
    que encara no existeix — fase 4) mai quadraria — els comptes 6xx/7xx
    del període encara no s'han traspassat enlloc del balanç. És la mateixa
    tècnica que fa servir qualsevol balanç de situació intermedi real."""
    _validar_mes(mes)
    fins = _fi_de_mes(year, mes)
    saldos = _saldos_per_tipus(db, (AccountType.actiu, AccountType.passiu, AccountType.patrimoni_net), data_fins=fins)

    resultat_pyg = _saldos_per_tipus(
        db, (AccountType.ingres, AccountType.despesa), data_fins=fins, data_des_de=date(year, 1, 1)
    )
    resultat_exercici = sum((l.saldo for l in resultat_pyg[AccountType.ingres]), Decimal("0")) - sum(
        (l.saldo for l in resultat_pyg[AccountType.despesa]), Decimal("0")
    )
    patrimoni_net = list(saldos[AccountType.patrimoni_net])
    if resultat_exercici != 0:
        patrimoni_net.append(
            BalancLiniaOut(compte_code="129*", compte_name="Resultat de l'exercici (provisional)", saldo=resultat_exercici)
        )

    total_actiu = sum((l.saldo for l in saldos[AccountType.actiu]), Decimal("0"))
    total_passiu_pn = sum((l.saldo for l in saldos[AccountType.passiu]), Decimal("0")) + sum(
        (l.saldo for l in patrimoni_net), Decimal("0")
    )
    return BalancSituacioOut(
        year=year, mes=mes, actiu=saldos[AccountType.actiu], passiu=saldos[AccountType.passiu],
        patrimoni_net=patrimoni_net, total_actiu=total_actiu,
        total_passiu_patrimoni_net=total_passiu_pn, quadrat=(total_actiu == total_passiu_pn),
    )


@router.get("/compte-resultats/{year}/{mes}", response_model=ComptePyGOut)
def compte_resultats(year: int, mes: int, db: Session = Depends(get_db)):
    """PyG NET d'IVA (700 sense el 477 que hi va lligat) — a diferència de
    `GET /admin/resultat/{y}/{m}`, que suma preus AMB IVA inclòs. Els dos
    informes responen preguntes diferents; no haurien de donar el mateix
    número (ver nota al capdamunt del fitxer)."""
    _validar_mes(mes)
    inici = date(year, mes, 1)
    fins = _fi_de_mes(year, mes)
    saldos = _saldos_per_tipus(db, (AccountType.ingres, AccountType.despesa), data_fins=fins, data_des_de=inici)

    total_ingressos = sum((l.saldo for l in saldos[AccountType.ingres]), Decimal("0"))
    total_despeses = sum((l.saldo for l in saldos[AccountType.despesa]), Decimal("0"))
    return ComptePyGOut(
        year=year, mes=mes,
        ingressos=[ComptePyGLiniaOut(compte_code=l.compte_code, compte_name=l.compte_name, total=l.saldo) for l in saldos[AccountType.ingres]],
        despeses=[ComptePyGLiniaOut(compte_code=l.compte_code, compte_name=l.compte_name, total=l.saldo) for l in saldos[AccountType.despesa]],
        total_ingressos=total_ingressos, total_despeses=total_despeses, resultat=total_ingressos - total_despeses,
    )

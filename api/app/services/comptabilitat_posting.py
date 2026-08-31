"""Motor de posting automàtic: genera assentaments de partida doble a partir
dels documents de negoci que ja existeixen (venda web, venda externa,
despesa, conciliació bancària, caixa diària) — l'usuari mai tecleja Debe/Haver
per a l'operativa diària, només per als ajustos manuals (fora d'abast
d'aquesta fase).

Cap funció d'aquí fa `db.commit()`: qui crida decideix quan (mateix criteri
que `services/reservations.py`), perquè l'assentament ha d'entrar a la
MATEIXA transacció que l'operació de negoci que el genera — si una falla,
l'altra tampoc es queda a mitges.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .comptabilitat_seed import ASSET_CATEGORY_ACCOUNT_ES, DESPESA_CATEGORY_ACCOUNT_ES
from ..models import (
    AccountingAccount, AssetDepreciationEntry, CaixaDiaria, Despesa, FixedAsset, JournalEntry, JournalEntryCounter,
    JournalLine, JournalSourceType, PeriodeComptable,
)


def next_entry_number(db: Session, fiscal_year: int) -> int:
    """Correlatiu per any fiscal, sense buits ni duplicats — UPDATE
    condicionat primer; si encara no existeix el comptador d'aquest any, es
    crea dins d'un SAVEPOINT (`begin_nested`) perquè una carrera concurrent
    (dos processos creant-lo alhora) no faci caure la transacció sencera,
    només aquest intent — mateix criteri que la reserva atòmica d'exemplars
    a services/reservations.py."""
    result = db.execute(
        update(JournalEntryCounter)
        .where(JournalEntryCounter.fiscal_year == fiscal_year)
        .values(next_number=JournalEntryCounter.next_number + 1)
        .returning(JournalEntryCounter.next_number)
        .execution_options(synchronize_session=False)
    )
    row = result.first()
    if row is not None:
        return row[0] - 1

    try:
        with db.begin_nested():
            db.add(JournalEntryCounter(fiscal_year=fiscal_year, next_number=2))
            db.flush()
        return 1
    except IntegrityError:
        result = db.execute(
            update(JournalEntryCounter)
            .where(JournalEntryCounter.fiscal_year == fiscal_year)
            .values(next_number=JournalEntryCounter.next_number + 1)
            .returning(JournalEntryCounter.next_number)
            .execution_options(synchronize_session=False)
        )
        return result.scalar_one() - 1


def _account_ids(db: Session, codes: set[str]) -> dict[str, int]:
    rows = db.execute(select(AccountingAccount.code, AccountingAccount.id).where(AccountingAccount.code.in_(codes))).all()
    found = {code: account_id for code, account_id in rows}
    missing = codes - found.keys()
    if missing:
        raise ValueError(f"Compte(s) no trobat(s) al pla de comptes d'aquest tenant: {', '.join(sorted(missing))}")
    return found


def post_entry(
    db: Session, *, entry_date: date, description: str, source_type: JournalSourceType,
    source_id: uuid.UUID | None, lines: list[tuple[str, Decimal, Decimal]],
) -> JournalEntry:
    """`lines`: llista de (codi_compte, debit, credit) — exactament un dels
    dos > 0 per línia (0 als dos es descarta, útil per a imports opcionals
    com el cost quan `Item.acquisition_cost` és desconegut). Aixeca
    `ValueError` si l'assentament no quadra o el període ja està tancat —
    l'entitat cridant NO fa el commit d'una operació de negoci amb un
    assentament descompensat: millor que falli tota l'operació."""
    lines_amb_import = [(code, d, c) for code, d, c in lines if d or c]
    total_debit = sum(d for _, d, _ in lines_amb_import)
    total_credit = sum(c for _, _, c in lines_amb_import)
    if total_debit != total_credit:
        raise ValueError(f"Assentament descompensat ({description}): deure={total_debit} haver={total_credit}")
    if not lines_amb_import:
        raise ValueError(f"Assentament sense cap import ({description})")

    periode = db.scalar(
        select(PeriodeComptable).where(
            PeriodeComptable.year == entry_date.year, PeriodeComptable.month == entry_date.month,
        )
    )
    if periode is not None and periode.closed:
        raise ValueError(f"El període {entry_date.month}/{entry_date.year} ja està tancat")

    entry_number = next_entry_number(db, entry_date.year)
    entry = JournalEntry(
        fiscal_year=entry_date.year, entry_number=entry_number, date=entry_date, description=description,
        source_type=source_type, source_id=source_id, period_id=periode.id if periode else None,
    )
    db.add(entry)
    db.flush()

    account_ids = _account_ids(db, {code for code, _, _ in lines_amb_import})
    for code, debit, credit in lines_amb_import:
        db.add(JournalLine(entry_id=entry.id, account_id=account_ids[code], debit=debit, credit=credit))
    db.flush()
    return entry


def unpost_source(db: Session, source_type: JournalSourceType, source_id: uuid.UUID) -> None:
    """Esborra els assentaments (i les seves línies, per cascade) generats
    prèviament per aquest document — usat per `caixa_diaria`, que és un
    upsert per dia i pot re-desar el mateix dia diverses vegades abans de
    tancar el període."""
    existents = db.scalars(
        select(JournalEntry).where(JournalEntry.source_type == source_type, JournalEntry.source_id == source_id)
    ).all()
    for entry in existents:
        db.delete(entry)
    if existents:
        db.flush()


def post_venda(
    db: Session, *, entry_date: date, source_type: JournalSourceType, source_id: uuid.UUID, description: str,
    total_collected: Decimal, revenue_base: Decimal, vat_amount: Decimal, cost: Decimal | None,
) -> JournalEntry:
    """Ingrés a compte de cobrar (430, no directe a caixa/banc — es cobra de
    veritat quan es concilia, ver post_cobrament_conciliacio) +, si es
    coneix el cost d'adquisició, la baixa d'existències (inventari
    permanent: 610/300 en cada venda, no només al tancament)."""
    lines: list[tuple[str, Decimal, Decimal]] = [
        ("430", total_collected, Decimal("0")),
        ("700", Decimal("0"), revenue_base),
        ("477", Decimal("0"), vat_amount),
    ]
    if cost:
        lines += [("610", cost, Decimal("0")), ("300", Decimal("0"), cost)]
    return post_entry(
        db, entry_date=entry_date, description=description, source_type=source_type, source_id=source_id,
        lines=lines,
    )


def post_cobrament_conciliacio(
    db: Session, *, entry_date: date, source_type: JournalSourceType, source_id: uuid.UUID, amount: Decimal,
    description: str,
) -> JournalEntry:
    """Cobrament confirmat d'una venda ja postejada (conciliació bancària, o
    agregat de caixa diària): tanca el 430 obert per `post_venda`."""
    return post_entry(
        db, entry_date=entry_date, description=description, source_type=source_type, source_id=source_id,
        lines=[("572", amount, Decimal("0")), ("430", Decimal("0"), amount)],
    )


def post_despesa_alta(db: Session, despesa: Despesa) -> JournalEntry:
    account_code = DESPESA_CATEGORY_ACCOUNT_ES.get(despesa.category.value, "629")
    lines: list[tuple[str, Decimal, Decimal]] = [(account_code, despesa.taxable_base, Decimal("0"))]
    if despesa.vat_amount:
        lines.append(("472", despesa.vat_amount, Decimal("0")))
    lines.append(("400", Decimal("0"), despesa.total))
    return post_entry(
        db, entry_date=despesa.invoice_date, description=f"Factura {despesa.supplier_name}: {despesa.concept}",
        source_type=JournalSourceType.despesa_alta, source_id=despesa.id, lines=lines,
    )


def post_despesa_pagament(
    db: Session, despesa: Despesa, *, payment_date: date, amount: Decimal, cash: bool,
) -> JournalEntry:
    tresoreria = "570" if cash else "572"
    return post_entry(
        db, entry_date=payment_date, description=f"Pagament factura {despesa.supplier_name}",
        source_type=JournalSourceType.despesa_pagament, source_id=despesa.id,
        lines=[("400", amount, Decimal("0")), (tresoreria, Decimal("0"), amount)],
    )


def post_actiu_alta(db: Session, actiu: FixedAsset) -> JournalEntry:
    account_code = ASSET_CATEGORY_ACCOUNT_ES[actiu.category.value]
    lines: list[tuple[str, Decimal, Decimal]] = [(account_code, actiu.acquisition_cost, Decimal("0"))]
    if actiu.vat_amount:
        lines.append(("472", actiu.vat_amount, Decimal("0")))
    lines.append(("400", Decimal("0"), actiu.acquisition_cost + actiu.vat_amount))
    return post_entry(
        db, entry_date=actiu.acquisition_date, description=f"Alta actiu: {actiu.name}",
        source_type=JournalSourceType.actiu_alta, source_id=actiu.id, lines=lines,
    )


def post_amortitzacio(db: Session, dep: AssetDepreciationEntry, actiu: FixedAsset) -> JournalEntry:
    entry_date = date(dep.year, dep.month, 1)
    return post_entry(
        db, entry_date=entry_date, description=f"Amortització {dep.month}/{dep.year}: {actiu.name}",
        source_type=JournalSourceType.actiu_amortitzacio, source_id=dep.id,
        lines=[("681", dep.amount, Decimal("0")), ("281", Decimal("0"), dep.amount)],
    )


def post_caixa_diaria(db: Session, caixa: CaixaDiaria) -> JournalEntry | None:
    """Idempotent: esborra el que hi hagués abans per aquest dia i el
    torna a postejar amb els totals actuals (l'endpoint és un upsert)."""
    unpost_source(db, JournalSourceType.caixa_diaria, caixa.id)

    cash_total = caixa.cash_21 + caixa.cash_4
    bank_total = (
        caixa.card_21 + caixa.card_4 + caixa.bizum_21 + caixa.bizum_4
        + caixa.paypal_21 + caixa.paypal_4 + caixa.transfer_21 + caixa.cultural_voucher
    )
    total = cash_total + bank_total
    if total == 0:
        return None

    lines: list[tuple[str, Decimal, Decimal]] = []
    if cash_total:
        lines.append(("570", cash_total, Decimal("0")))
    if bank_total:
        lines.append(("572", bank_total, Decimal("0")))
    lines.append(("430", Decimal("0"), total))
    return post_entry(
        db, entry_date=caixa.date, description=f"Caixa diària {caixa.date.isoformat()}",
        source_type=JournalSourceType.caixa_diaria, source_id=caixa.id, lines=lines,
    )

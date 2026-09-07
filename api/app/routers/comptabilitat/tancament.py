"""Tancament d'exercici formal (docs/PLAN_PARIDAD_HOLDED.md B5,
docs/MEJORAS_COMPTABILITAT.md): un únic assentament de regularització,
datat 31/12, que salda contra el compte 129 tots els comptes d'ingrés/
despesa amb saldo no nul de l'any, més el tancament dels 12 períodes
mensuals d'aquell any.

No hi ha assentament d'obertura de l'exercici següent (ver migració
909c657203ee): el balanç de situació ja calcula els saldos patrimonials de
forma acumulada des de l'origen, no any a any — arrosseguen sols un cop
existeix l'assentament de regularització.

"Exercici tancat" no és cap flag nou: es dedueix de si ja existeix un
assentament amb source_type `tancament_exercici` per aquell any."""

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import AccountType, JournalEntry, JournalSourceType
from ...schemas import AssentamentLlibreOut
from ...services.comptabilitat_posting import post_entry
from ...services.security import require_admin
from .llibres import _assentament_out, _saldos_per_tipus
from .periodes import _get_or_create_periode

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


def _assentament_tancament(db: Session, year: int) -> JournalEntry | None:
    return db.scalar(
        select(JournalEntry).where(
            JournalEntry.fiscal_year == year, JournalEntry.source_type == JournalSourceType.tancament_exercici,
        )
    )


@router.post("/periodes/{year}/tancar-exercici", response_model=AssentamentLlibreOut, status_code=201)
def tancar_exercici(year: int, db: Session = Depends(get_db)):
    if _assentament_tancament(db, year) is not None:
        raise HTTPException(409, f"L'exercici {year} ja està tancat")

    resultat_pyg = _saldos_per_tipus(
        db, (AccountType.ingres, AccountType.despesa), data_fins=date(year, 12, 31), data_des_de=date(year, 1, 1),
    )

    # Saldar cada compte d'ingrés (normal haver) a zero -> debitar-lo pel seu
    # saldo; cada compte de despesa (normal deure) -> creditar-lo. La
    # diferència neta la rep el 129 (mateixa agregació que ja mostra
    # `compte_resultats`/`balanc_situacio`, per no poder-se desviar mai
    # d'allò que l'usuari ja ha vist tot l'any).
    lines: list[tuple[str, Decimal, Decimal]] = [
        (l.compte_code, l.saldo, Decimal("0")) for l in resultat_pyg[AccountType.ingres]
    ] + [
        (l.compte_code, Decimal("0"), l.saldo) for l in resultat_pyg[AccountType.despesa]
    ]
    resultat_exercici = sum((l.saldo for l in resultat_pyg[AccountType.ingres]), Decimal("0")) - sum(
        (l.saldo for l in resultat_pyg[AccountType.despesa]), Decimal("0")
    )
    if resultat_exercici > 0:
        lines.append(("129", Decimal("0"), resultat_exercici))
    elif resultat_exercici < 0:
        lines.append(("129", -resultat_exercici, Decimal("0")))

    try:
        entry = post_entry(
            db, entry_date=date(year, 12, 31),
            description=f"Regularització de resultats de l'exercici {year}",
            source_type=JournalSourceType.tancament_exercici, source_id=None, lines=lines,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    for mes in range(1, 13):
        p = _get_or_create_periode(year, mes, db)
        if not p.closed:
            p.closed = True
            p.closed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(entry)
    return _assentament_out(entry)


@router.post("/periodes/{year}/reobrir-exercici", status_code=204)
def reobrir_exercici(year: int, db: Session = Depends(get_db)):
    """Desfà `tancar_exercici`: esborra l'assentament de regularització i
    reobre els 12 períodes de l'any. Simètric a `obrir_periode`/`tancar_periode`
    per a un mes individual."""
    entry = _assentament_tancament(db, year)
    if entry is None:
        raise HTTPException(404, f"L'exercici {year} no està tancat")

    db.delete(entry)
    for mes in range(1, 13):
        p = _get_or_create_periode(year, mes, db)
        p.closed = False
        p.closed_at = None
    db.commit()

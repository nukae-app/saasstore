from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import PeriodeComptable
from ...schemas import PeriodeComptableOut
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


@router.get("/periodes", response_model=list[PeriodeComptableOut])
def list_periodes(db: Session = Depends(get_db)):
    return db.scalars(
        select(PeriodeComptable).order_by(PeriodeComptable.year.desc(), PeriodeComptable.month.desc())
    ).all()


def _get_or_create_periode(year: int, mes: int, db: Session) -> PeriodeComptable:
    periode = db.scalar(
        select(PeriodeComptable).where(PeriodeComptable.year == year, PeriodeComptable.month == mes)
    )
    if periode is None:
        periode = PeriodeComptable(year=year, month=mes)
        db.add(periode)
        db.flush()
    return periode


@router.post("/periodes/{year}/{mes}/tancar", response_model=PeriodeComptableOut)
def tancar_periode(year: int, mes: int, db: Session = Depends(get_db)):
    p = _get_or_create_periode(year, mes, db)
    if p.closed:
        raise HTTPException(409, "El mes ja estava tancat")
    p.closed = True
    p.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    return p


@router.post("/periodes/{year}/{mes}/obrir", response_model=PeriodeComptableOut)
def obrir_periode(year: int, mes: int, db: Session = Depends(get_db)):
    p = _get_or_create_periode(year, mes, db)
    p.closed = False
    p.closed_at = None
    db.commit()
    db.refresh(p)
    return p


@router.patch("/periodes/{year}/{mes}/notes", response_model=PeriodeComptableOut)
def update_notes_periode(year: int, mes: int, notes: str, db: Session = Depends(get_db)):
    p = _get_or_create_periode(year, mes, db)
    p.notes = notes
    db.commit()
    db.refresh(p)
    return p

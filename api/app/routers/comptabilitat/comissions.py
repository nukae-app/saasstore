"""CRUD de comissions bancàries de cobrament per canal (ver
docs/PLAN_COBRAMENTS_PAGAMENTS.md) — configura si i com es descompta la
comissió de targeta al tancar el 430 (`services/comptabilitat_posting.py::
calcula_comissio`), sense tocar cap altre flux."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import CanalComissio, ComissioPagament
from ...schemas import ComissioPagamentIn, ComissioPagamentOut
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["comptabilitat"], dependencies=[Depends(require_admin)])


@router.post("/comissions-pagament", status_code=201, response_model=ComissioPagamentOut)
def create_comissio(payload: ComissioPagamentIn, db: Session = Depends(get_db)):
    existent = db.scalar(select(ComissioPagament).where(ComissioPagament.canal == CanalComissio(payload.canal)))
    if existent is not None:
        raise HTTPException(409, f"Ja existeix una configuració de comissió per al canal '{payload.canal}'")
    comissio = ComissioPagament(**payload.model_dump())
    db.add(comissio)
    db.commit()
    db.refresh(comissio)
    return comissio


@router.get("/comissions-pagament", response_model=list[ComissioPagamentOut])
def list_comissions(db: Session = Depends(get_db)):
    return db.scalars(select(ComissioPagament).order_by(ComissioPagament.canal)).all()


@router.patch("/comissions-pagament/{comissio_id}", response_model=ComissioPagamentOut)
def update_comissio(comissio_id: int, payload: ComissioPagamentIn, db: Session = Depends(get_db)):
    comissio = db.get(ComissioPagament, comissio_id)
    if comissio is None:
        raise HTTPException(404, "Configuració de comissió no trobada")
    for k, v in payload.model_dump().items():
        setattr(comissio, k, v)
    db.commit()
    db.refresh(comissio)
    return comissio


@router.delete("/comissions-pagament/{comissio_id}", status_code=204)
def delete_comissio(comissio_id: int, db: Session = Depends(get_db)):
    comissio = db.get(ComissioPagament, comissio_id)
    if comissio is None:
        raise HTTPException(404, "Configuració de comissió no trobada")
    db.delete(comissio)
    db.commit()

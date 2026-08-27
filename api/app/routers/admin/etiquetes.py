import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import Etiqueta, Release, ReleaseEtiqueta
from ...schemas import EtiquetaIn, EtiquetaOut
from ...services.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/etiquetes", response_model=list[EtiquetaOut])
def list_etiquetes(db: Session = Depends(get_db)):
    return db.scalars(select(Etiqueta).order_by(Etiqueta.position, Etiqueta.id)).all()


@router.post("/etiquetes", response_model=EtiquetaOut, status_code=201)
def create_etiqueta(payload: EtiquetaIn, db: Session = Depends(get_db)):
    if db.scalar(select(Etiqueta).where(Etiqueta.slug == payload.slug)):
        raise HTTPException(409, f"Ja existeix una etiqueta amb el slug '{payload.slug}'")
    etiqueta = Etiqueta(**payload.model_dump())
    db.add(etiqueta)
    db.commit()
    db.refresh(etiqueta)
    return etiqueta


@router.put("/etiquetes/{etiqueta_id}", response_model=EtiquetaOut)
def update_etiqueta(etiqueta_id: int, payload: EtiquetaIn, db: Session = Depends(get_db)):
    etiqueta = db.get(Etiqueta, etiqueta_id)
    if etiqueta is None:
        raise HTTPException(404, "Etiqueta no trobada")
    conflict = db.scalar(
        select(Etiqueta).where(Etiqueta.slug == payload.slug, Etiqueta.id != etiqueta_id)
    )
    if conflict:
        raise HTTPException(409, f"Ja existeix una etiqueta amb el slug '{payload.slug}'")
    for k, v in payload.model_dump().items():
        setattr(etiqueta, k, v)
    db.commit()
    db.refresh(etiqueta)
    return etiqueta


@router.delete("/etiquetes/{etiqueta_id}", status_code=204)
def delete_etiqueta(etiqueta_id: int, db: Session = Depends(get_db)):
    etiqueta = db.get(Etiqueta, etiqueta_id)
    if etiqueta is None:
        raise HTTPException(404, "Etiqueta no trobada")
    db.delete(etiqueta)
    db.commit()


@router.get("/releases/{release_id}/etiquetes", response_model=list[EtiquetaOut])
def get_release_etiquetes(release_id: uuid.UUID, db: Session = Depends(get_db)):
    release = db.scalar(
        select(Release).options(selectinload(Release.etiquetes)).where(Release.id == release_id)
    )
    if release is None:
        raise HTTPException(404, "Release no trobat")
    return release.etiquetes


class _EtiquetaIdsBody(BaseModel):
    etiqueta_ids: list[int] = []


@router.put("/releases/{release_id}/etiquetes")
def set_release_etiquetes(release_id: uuid.UUID, body: _EtiquetaIdsBody, db: Session = Depends(get_db)):
    """Substitueix totes les etiquetes del release per la llista donada."""
    if not db.get(Release, release_id):
        raise HTTPException(404, "Release no trobat")
    db.execute(delete(ReleaseEtiqueta).where(ReleaseEtiqueta.release_id == release_id))
    for eid in body.etiqueta_ids:
        if db.get(Etiqueta, eid):
            db.add(ReleaseEtiqueta(release_id=release_id, etiqueta_id=eid))
    db.commit()
    return {"etiqueta_ids": body.etiqueta_ids}

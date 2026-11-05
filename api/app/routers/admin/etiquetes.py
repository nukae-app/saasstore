import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import CondicionItem, Etiqueta, ItemStatus, RecordProduct, Release, ReleaseEtiqueta
from ...schemas import EtiquetaIn, EtiquetaOut
from ...services.security import require_admin
from .releases import _release_filters

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


class _Criteris(BaseModel):
    """Mateixos filtres que GET /admin/releases (vegeu `_release_filters`)."""

    q: str | None = None
    artista: list[str] | None = None
    sello: list[str] | None = None
    formato: list[str] | None = None
    genero: list[str] | None = None
    estilo: list[str] | None = None
    pais: list[str] | None = None
    anio: list[int] | None = None
    anio_min: int | None = None
    anio_max: int | None = None
    etiqueta: list[str] | None = None
    seccio: list[str] | None = None
    status: list[ItemStatus] | None = None
    condicion: list[CondicionItem] | None = None
    estado_disco: list[str] | None = None
    precio_min: float | None = None
    precio_max: float | None = None
    con_stock: bool | None = None
    stock_bajo: bool | None = None
    sin_imagen: bool | None = None
    sin_discogs: bool | None = None
    sin_seccio: bool | None = None


class _AssignarBody(BaseModel):
    accio: Literal["afegir", "treure"] = "afegir"
    release_ids: list[uuid.UUID] | None = None
    criteris: _Criteris | None = None
    # Només compta (no modifica): per mostrar «s'aplicarà a N discos».
    previsualitzar: bool = False


@router.post("/etiquetes/{etiqueta_id}/assignar")
def assignar_etiqueta(etiqueta_id: int, body: _AssignarBody, db: Session = Depends(get_db)):
    """Afegeix o treu l'etiqueta a molts discos d'una tacada.

    Els discos s'indiquen amb `release_ids` (selecció manual) o amb `criteris`
    (els mateixos filtres del catàleg admin). Idempotent: afegir un disc que ja
    la té, o treure'n un que no, no és error.
    """
    if not db.get(Etiqueta, etiqueta_id):
        raise HTTPException(404, "Etiqueta no trobada")
    if (body.release_ids is None) == (body.criteris is None):
        raise HTTPException(422, "Cal indicar release_ids o criteris (només un)")

    if body.criteris is not None:
        filters = _release_filters(**body.criteris.model_dump())
        stmt = select(Release.id).outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
        if filters:
            stmt = stmt.where(*filters)
        target_ids = set(db.scalars(stmt).all())
    else:
        wanted = set(body.release_ids)
        target_ids = set(db.scalars(select(Release.id).where(Release.id.in_(wanted))).all()) if wanted else set()

    already = set(
        db.scalars(
            select(ReleaseEtiqueta.release_id).where(ReleaseEtiqueta.etiqueta_id == etiqueta_id)
        ).all()
    ) & target_ids
    to_change = (target_ids - already) if body.accio == "afegir" else already

    if not body.previsualitzar and to_change:
        if body.accio == "afegir":
            db.add_all(ReleaseEtiqueta(release_id=rid, etiqueta_id=etiqueta_id) for rid in to_change)
        else:
            db.execute(
                delete(ReleaseEtiqueta).where(
                    ReleaseEtiqueta.etiqueta_id == etiqueta_id,
                    ReleaseEtiqueta.release_id.in_(to_change),
                )
            )
        db.commit()

    return {
        "coincidents": len(target_ids),
        "afectats": len(to_change),
        "ja_estaven": len(already) if body.accio == "afegir" else len(target_ids) - len(already),
        "aplicat": not body.previsualitzar,
    }

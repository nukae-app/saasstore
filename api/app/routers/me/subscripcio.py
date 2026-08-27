from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import (
    Address, Assignacio, EstatAssignacio, EstatSubscripcio, RecordProduct, Release, Subscripcio, User,
)
from ...schemas import SubscripcioMeOut, SubscripcioMePatch
from ...services.security import get_current_user

router = APIRouter(prefix="/me", tags=["me"])


def _get_own_subscripcio_or_404(db: Session, user: User) -> Subscripcio:
    subscripcio = db.scalar(
        select(Subscripcio)
        .where(Subscripcio.user_id == user.id, Subscripcio.estat != EstatSubscripcio.cancel_lada)
    )
    if subscripcio is None:
        raise HTTPException(404, "No tens cap subscripció")
    return subscripcio


def _subscripcio_me_dict(db: Session, subscripcio: Subscripcio) -> dict:
    discos_rebuts = list(db.execute(
        select(Release.id, RecordProduct.artista, Release.title, Release.image_url, Assignacio.confirmada_at)
        .join(Assignacio, Assignacio.release_id == Release.id)
        .outerjoin(RecordProduct, RecordProduct.release_id == Release.id)
        .where(Assignacio.subscripcio_id == subscripcio.id, Assignacio.estat == EstatAssignacio.confirmada)
        .order_by(Assignacio.confirmada_at.desc())
    ).all())
    return {
        "id": subscripcio.id,
        "estat": subscripcio.estat,
        "periodicitat_mesos": subscripcio.periodicitat_mesos,
        "quantitat": subscripcio.quantitat,
        "preu_periode": subscripcio.preu_periode,
        "generes_preferits": subscripcio.generes_preferits,
        "proxima_facturacio": subscripcio.proxima_facturacio,
        "discos_rebuts": [
            {"release_id": r[0], "artista": r[1], "titulo": r[2], "imagen_url": r[3], "confirmada_at": r[4]}
            for r in discos_rebuts
        ],
    }


@router.get("/subscripcio", response_model=SubscripcioMeOut)
def get_subscripcio(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subscripcio = _get_own_subscripcio_or_404(db, user)
    return _subscripcio_me_dict(db, subscripcio)


@router.patch("/subscripcio", response_model=SubscripcioMeOut)
def patch_subscripcio(
    payload: SubscripcioMePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscripcio = _get_own_subscripcio_or_404(db, user)
    if subscripcio.estat == EstatSubscripcio.pendent_pagament:
        raise HTTPException(409, "Encara no s'ha confirmat el pagament d'aquesta subscripció")

    if payload.estat is not None:
        if payload.estat not in ("activa", "pausada"):
            raise HTTPException(422, "Estat no vàlid")
        subscripcio.estat = EstatSubscripcio(payload.estat)
    if payload.generes_preferits is not None:
        subscripcio.generes_preferits = payload.generes_preferits
    if payload.address_id is not None:
        address = db.get(Address, payload.address_id)
        if address is None or address.user_id != user.id:
            raise HTTPException(404, "Adreça no trobada")
        subscripcio.address_id = address.id

    db.commit()
    return _subscripcio_me_dict(db, subscripcio)


@router.post("/subscripcio/cancelar", response_model=SubscripcioMeOut)
def cancelar_subscripcio(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subscripcio = _get_own_subscripcio_or_404(db, user)
    subscripcio.estat = EstatSubscripcio.cancel_lada
    subscripcio.cancel_lada_at = datetime.now(timezone.utc)
    db.commit()
    return _subscripcio_me_dict(db, subscripcio)

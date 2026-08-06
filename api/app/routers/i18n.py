"""Endpoint público para servir traducciones de la UI por idioma."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Translation

router = APIRouter(prefix="/i18n", tags=["i18n"])

SUPPORTED = {"ca", "es", "en"}


@router.get("/{lang}")
def get_translations(lang: str, db: Session = Depends(get_db)):
    if lang not in SUPPORTED:
        raise HTTPException(400, f"Idioma no soportado. Usa: {', '.join(sorted(SUPPORTED))}")
    rows = db.scalars(select(Translation).where(Translation.lang == lang)).all()
    return {r.key: r.value for r in rows}

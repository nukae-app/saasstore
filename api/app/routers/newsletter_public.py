"""Baixa (unsubscribe) pública des de l'enllaç del correu de newsletter."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import NewsletterSend, User
from ..services.security import _hash

router = APIRouter(prefix="/newsletter", tags=["newsletter"])


@router.get("/baixa")
def unsubscribe(token: str = Query(...), db: Session = Depends(get_db)):
    enviament = db.scalar(select(NewsletterSend).where(NewsletterSend.unsubscribe_token_hash == _hash(token)))
    if enviament is None:
        raise HTTPException(404, "Enllaç de baixa invàlid")
    if enviament.user_id is not None:
        user = db.get(User, enviament.user_id)
        if user is not None:
            user.consent_newsletter = False
            db.commit()
    return {"ok": True}

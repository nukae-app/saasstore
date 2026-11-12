"""Baixa (unsubscribe) pública des de l'enllaç del correu de newsletter.

Dos passos a propòsit: el GET només valida el token (els escàners d'enllaços i
els antivirus dels correus visiten els GET i donarien de baixa tothom); el POST
és qui efectivament retira el consentiment. El POST també és el que crida la
baixa en un clic de Gmail/Yahoo (RFC 8058, capçalera `List-Unsubscribe-Post`),
que envia el cos `List-Unsubscribe=One-Click`."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import NewsletterSend, User
from ..services.security import _hash

router = APIRouter(prefix="/newsletter", tags=["newsletter"])


def _enviament_or_404(db: Session, token: str) -> NewsletterSend:
    enviament = db.scalar(select(NewsletterSend).where(NewsletterSend.unsubscribe_token_hash == _hash(token)))
    if enviament is None:
        raise HTTPException(404, "Enllaç de baixa invàlid")
    return enviament


@router.get("/baixa")
def check_unsubscribe_token(token: str = Query(...), db: Session = Depends(get_db)):
    """Només comprova que l'enllaç és vàlid; no canvia res."""
    _enviament_or_404(db, token)
    return {"ok": True, "confirmed": False}


@router.post("/baixa")
def unsubscribe(token: str = Query(...), db: Session = Depends(get_db)):
    enviament = _enviament_or_404(db, token)
    if enviament.user_id is not None:
        user = db.get(User, enviament.user_id)
        if user is not None:
            user.consent_newsletter = False
            db.commit()
    return {"ok": True, "confirmed": True}

"""Gestió i enviament de newsletters des del panell d'administració."""

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import NewsletterCampaign, NewsletterCampaignStatus, NewsletterSend, NewsletterSendStatus, User
from ..services.emailer import absolutize_upload_urls, send_email
from ..services.security import require_admin
from ..tasks.newsletter import send_campaign

UPLOADS_DIR = "/app/uploads"

router = APIRouter(prefix="/admin/newsletter", tags=["admin-newsletter"], dependencies=[Depends(require_admin)])


class CampaignCreateIn(BaseModel):
    subject: str
    content_html: str
    language: str = "ca"


class CampaignPatchIn(BaseModel):
    subject: str | None = None
    content_html: str | None = None
    language: str | None = None


class SendTestIn(BaseModel):
    email: EmailStr


def _campaign_dict(c: NewsletterCampaign, counts: dict[str, int]) -> dict:
    return {
        "id": c.id,
        "subject": c.subject,
        "content_html": c.content_html,
        "language": c.language,
        "status": c.status,
        "created_at": c.created_at,
        "sending_started_at": c.sending_started_at,
        "sending_finished_at": c.sending_finished_at,
        "counts": {
            "pendent": counts.get(NewsletterSendStatus.pendent.value, 0),
            "enviat": counts.get(NewsletterSendStatus.enviat.value, 0),
            "error": counts.get(NewsletterSendStatus.error.value, 0),
        },
    }


def _counts_for(db: Session, campaign_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(NewsletterSend.status, func.count(NewsletterSend.id))
        .where(NewsletterSend.campaign_id == campaign_id)
        .group_by(NewsletterSend.status)
    ).all()
    return {status.value: n for status, n in rows}


@router.get("/recipients/count")
def count_recipients(db: Session = Depends(get_db)):
    total = db.scalar(
        select(func.count(User.id)).where(User.active == True, User.consent_newsletter == True)
    )
    return {"total": total}


@router.post("/images")
async def upload_image(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        raise HTTPException(422, "Només s'accepten imatges JPG, PNG, WebP o GIF")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    return {"url": f"/uploads/{filename}"}


@router.get("")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.scalars(select(NewsletterCampaign).order_by(NewsletterCampaign.created_at.desc())).all()
    return [_campaign_dict(c, _counts_for(db, c.id)) for c in campaigns]


@router.post("", status_code=201)
def create_campaign(payload: CampaignCreateIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = NewsletterCampaign(
        subject=payload.subject,
        content_html=payload.content_html,
        language=payload.language,
        creat_by_id=admin.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _campaign_dict(c, {})


@router.get("/{campaign_id}")
def get_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(NewsletterCampaign, campaign_id)
    if c is None:
        raise HTTPException(404, "Campanya no trobada")
    d = _campaign_dict(c, _counts_for(db, c.id))
    errors = db.scalars(
        select(NewsletterSend)
        .where(NewsletterSend.campaign_id == c.id, NewsletterSend.status == NewsletterSendStatus.error)
        .limit(20)
    ).all()
    d["errors"] = [{"email": e.email, "error_msg": e.error_msg} for e in errors]
    return d


@router.patch("/{campaign_id}")
def update_campaign(campaign_id: uuid.UUID, payload: CampaignPatchIn, db: Session = Depends(get_db)):
    c = db.get(NewsletterCampaign, campaign_id)
    if c is None:
        raise HTTPException(404, "Campanya no trobada")
    if c.status != NewsletterCampaignStatus.esborrany:
        raise HTTPException(409, "Només es pot editar una campanya en esborrany")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(c, field, val)
    db.commit()
    db.refresh(c)
    return _campaign_dict(c, _counts_for(db, c.id))


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(NewsletterCampaign, campaign_id)
    if c is None:
        raise HTTPException(404, "Campanya no trobada")
    if c.status != NewsletterCampaignStatus.esborrany:
        raise HTTPException(409, "Només es pot esborrar una campanya en esborrany")
    db.delete(c)
    db.commit()


@router.post("/{campaign_id}/send-test")
def send_test(campaign_id: uuid.UUID, payload: SendTestIn, request: Request, db: Session = Depends(get_db)):
    c = db.get(NewsletterCampaign, campaign_id)
    if c is None:
        raise HTTPException(404, "Campanya no trobada")
    send_email(
        to=payload.email,
        subject=f"[PROVA] {c.subject}",
        body=f"{c.subject}\n\n(Correu de prova, no s'ha enviat a cap subscriptor.)",
        tenant=request.state.tenant,
        db=db,
        html=absolutize_upload_urls(c.content_html, request.state.tenant),
    )
    return {"ok": True}


@router.post("/{campaign_id}/send", status_code=202)
def send(campaign_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    c = db.get(NewsletterCampaign, campaign_id)
    if c is None:
        raise HTTPException(404, "Campanya no trobada")
    if c.status != NewsletterCampaignStatus.esborrany:
        raise HTTPException(409, "La campanya ja s'ha enviat o s'està enviant")
    c.status = NewsletterCampaignStatus.enviant
    c.sending_started_at = datetime.now(timezone.utc)
    db.commit()
    # `NewsletterCampaign` en sí no lleva tenant_id todavía (funcionalidad
    # aplazada desde la Fase 1), pero `User` sí — sin pasar el tenant, la
    # tarea (que abre su propia sesión sin contexto, ver tasks/newsletter.py)
    # consultaría TODOS los usuarios de TODOS los tenants con
    # consent_newsletter=True, no solo los de este.
    send_campaign.delay(str(c.id), str(request.state.tenant.id))
    return {"ok": True}

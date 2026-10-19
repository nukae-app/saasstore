import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...config import get_settings
from ...database import get_db
from ...models import User
from ...rate_limit import limiter
from ...services.gdpr import ErasureBlocked, anonymize_user, export_user_data
from ...services.security import REFRESH_COOKIE, get_current_user, verify_password

router = APIRouter(prefix="/me", tags=["me"])


class ProfilePatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    language: str | None = None
    consent_newsletter: bool | None = None


class MeFullOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    phone: str | None
    role: str
    language: str
    consent_newsletter: bool
    active: bool

    model_config = {"from_attributes": True}


@router.get("/profile", response_model=MeFullOut)
def get_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/profile", response_model=MeFullOut)
def update_profile(
    payload: ProfilePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, val)
    db.commit()
    db.refresh(user)
    return user


@router.get("/data-export")
@limiter.limit("5/hour")
def data_export(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Derecho de acceso y portabilidad (RGPD art. 15 y 20): descarga en JSON
    de todo lo que guardamos sobre la cuenta."""
    body = json.dumps(export_user_data(db, user), ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="les-meves-dades.json"'},
    )


class DeleteAccountIn(BaseModel):
    # Confirmación explícita: hay que escribir el propio email. Si la cuenta
    # tiene contraseña, además se exige (un token robado no basta para borrarla).
    confirm_email: str
    password: str | None = None


@router.delete("")
@limiter.limit("5/hour")
def delete_account(
    request: Request,
    payload: DeleteAccountIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Derecho de supresión (RGPD art. 17). Anonimiza la cuenta conservando
    solo lo que la ley obliga a guardar (ver services/gdpr.py)."""
    if payload.confirm_email.strip().lower() != user.email.lower():
        raise HTTPException(422, "L'email de confirmació no coincideix")
    if user.password_hash and not (payload.password and verify_password(payload.password, user.password_hash)):
        raise HTTPException(403, "Contrasenya incorrecta")
    try:
        anonymize_user(db, user)
    except ErasureBlocked as e:
        return JSONResponse(status_code=409, content={"detail": "No es pot esborrar encara", "reasons": e.reasons})
    resp = Response(status_code=204)
    resp.delete_cookie(REFRESH_COOKIE, path=get_settings().refresh_cookie_path)
    return resp

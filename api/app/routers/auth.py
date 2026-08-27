"""Autenticación sin contraseñas: Google (OpenID Connect) + magic link.

En ambos casos el resultado es el mismo: se crea/recupera el usuario por
email y se emite NUESTRA sesión (access token JWT corto + refresh token
en cookie httpOnly). Google solo prueba la identidad en el momento del
login; no guardamos ningún token de Google.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import AuthToken, Identity, Tenant, User
from ..rate_limit import limiter
from ..schemas import MagicLinkRequest, MeOut, PasswordLoginRequest, RegisterRequest, SetPasswordRequest, TokenOut
from ..services.emailer import render_email_html, send_email
from ..services.i18n import translate
from ..tenancy import tenant_frontend_url
from ..services.security import (
    REFRESH_COOKIE,
    as_utc,
    create_access_token,
    get_current_user,
    get_refresh_cookie,
    hash_password,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_settings = get_settings()
oauth = OAuth()
oauth.register(
    name="google",
    client_id=_settings.google_client_id,
    client_secret=_settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
)


def _get_or_create_user(db: Session, email: str, nombre: str | None = None, idioma: str | None = None) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        # email_verified=True: la posesión del email ya queda probada por el propio
        # flujo (magic link canjeado o Google con email_verified=True en el id_token).
        user = User(email=email.lower(), name=nombre, email_verified=True, language=idioma or "ca")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _send_verification_email(db: Session, email: str, tenant: Tenant, idioma: str = "ca") -> None:
    raw = secrets.token_urlsafe(32)
    hours = get_settings().email_verification_hours
    db.add(
        AuthToken(
            email=email.lower(),
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            purpose="verify_email",
            idioma=idioma,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
        )
    )
    db.commit()
    link = f"{tenant_frontend_url(tenant)}/{idioma}/auth/verify-email?token={raw}"
    body = translate(db, "email.verify_email.body_text", idioma, hours=hours, link=link, nom=tenant.nombre)
    html = render_email_html(
        translate(db, "email.verify_email.heading", idioma, nom=tenant.nombre),
        translate(db, "email.verify_email.body_html", idioma, hours=hours, link=link),
        tenant, db,
        cta=(translate(db, "email.verify_email.cta", idioma), link),
    )
    send_email(
        email,
        translate(db, "email.verify_email.subject", idioma, nom=tenant.nombre),
        body,
        tenant,
        db,
        html=html,
    )


def _set_session(response: Response, db: Session, user: User) -> TokenOut:
    raw_refresh = issue_refresh_token(db, user)
    response.set_cookie(
        REFRESH_COOKIE,
        raw_refresh,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=get_settings().refresh_token_days * 86400,
        path=get_settings().refresh_cookie_path,
    )
    return TokenOut(access_token=create_access_token(user))


# --- Password auth ---

@router.post("/register", status_code=202)
@limiter.limit("10/hour")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(409, "Aquest email ja té un compte")
    if len(payload.password) < 8:
        raise HTTPException(422, "La contrasenya ha de tenir mínim 8 caràcters")
    user = User(
        email=payload.email.lower(),
        name=payload.name or None,
        password_hash=hash_password(payload.password),
        email_verified=False,
        language=payload.language,
    )
    db.add(user)
    db.commit()
    _send_verification_email(db, user.email, request.state.tenant, idioma=payload.language)
    return {"detail": "Compte creat. Revisa el teu email per activar-lo."}


@router.post("/resend-verification", status_code=202)
@limiter.limit("10/hour")
def resend_verification(request: Request, payload: MagicLinkRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is not None and not user.email_verified:
        _send_verification_email(db, user.email, request.state.tenant, idioma=user.language)
    # 202 siempre: no revelamos si el email existe o ya estaba verificado
    return {"detail": "Si el compte existeix i encara no està activat, rebràs un email"}


@router.post("/verify-email", response_model=TokenOut)
def verify_email(token: str, response: Response, db: Session = Depends(get_db)):
    row = db.scalar(
        select(AuthToken).where(
            AuthToken.token_hash == hashlib.sha256(token.encode()).hexdigest(),
            AuthToken.purpose == "verify_email",
        )
    )
    now = datetime.now(timezone.utc)
    if row is None or row.used_at is not None or as_utc(row.expires_at) < now:
        raise HTTPException(400, "Enlace inválido o caducado, pide uno nuevo")
    user = db.scalar(select(User).where(User.email == row.email))
    if user is None:
        raise HTTPException(400, "Enlace inválido o caducado, pide uno nuevo")
    row.used_at = now
    user.email_verified = True
    db.commit()
    return _set_session(response, db, user)


@router.post("/login", response_model=TokenOut)
@limiter.limit("20/hour")
def login(request: Request, payload: PasswordLoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email o contrasenya incorrectes")
    if not user.active:
        raise HTTPException(403, "Compte desactivat")
    if not user.email_verified:
        raise HTTPException(403, "Confirma el teu email abans d'entrar, revisa la safata d'entrada")
    return _set_session(response, db, user)


@router.post("/set-password", status_code=204)
def set_password(
    payload: SetPasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if len(payload.password) < 8:
        raise HTTPException(422, "La contrasenya ha de tenir mínim 8 caràcters")
    user.password_hash = hash_password(payload.password)
    db.commit()


# --- Google ---

@router.get("/google/login")
async def google_login(request: Request, locale: str = "ca"):
    # El idioma actual del visitante viaja en la sesión (cookie propia, ya
    # requerida por authlib para el state/nonce de OAuth) porque el único
    # dato que sobrevive el viaje de ida y vuelta a Google es lo que
    # guardemos nosotros mismos: el `state` de OAuth lo genera y verifica
    # authlib, no es sitio para colar datos propios.
    request.session["oauth_locale"] = locale if locale in {"ca", "es", "en"} else "ca"
    redirect_uri = str(request.url_for("google_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    info = token.get("userinfo") or {}
    if not info.get("email") or not info.get("email_verified"):
        raise HTTPException(400, "Google no ha devuelto un email verificado")

    locale = request.session.pop("oauth_locale", "ca")
    sub = info["sub"]
    identity = db.scalar(
        select(Identity).where(Identity.provider == "google", Identity.provider_user_id == sub)
    )
    if identity is not None:
        user = db.get(User, identity.user_id)
    else:
        # Vinculación por email verificado: si ya existe cuenta con ese email, se enlaza
        user = _get_or_create_user(db, info["email"], info.get("name"), idioma=locale)
        db.add(Identity(user_id=user.id, provider="google", provider_user_id=sub))
        db.commit()

    response = RedirectResponse(url=f"{tenant_frontend_url(request.state.tenant)}/{locale}/auth/ok")
    _set_session(response, db, user)
    return response


# --- Magic link ---

@router.post("/magic-link", status_code=202)
@limiter.limit("10/hour")
def request_magic_link(request: Request, payload: MagicLinkRequest, db: Session = Depends(get_db)):
    raw = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            email=payload.email.lower(),
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            purpose="magic_link",
            idioma=payload.language,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=get_settings().magic_link_minutes),
        )
    )
    db.commit()
    link = f"{tenant_frontend_url(request.state.tenant)}/{payload.language}/auth/magic?token={raw}"
    minuts = get_settings().magic_link_minutes
    send_email(
        payload.email,
        translate(db, "email.magic_link.subject", payload.language, nom=request.state.tenant.nombre),
        translate(db, "email.magic_link.body_text", payload.language, minuts=minuts, link=link),
        request.state.tenant,
        db,
        html=render_email_html(
            translate(db, "email.magic_link.heading", payload.language),
            translate(db, "email.magic_link.body_html", payload.language, minuts=minuts),
            request.state.tenant, db,
            cta=(translate(db, "email.magic_link.cta", payload.language), link),
        ),
    )
    # 202 siempre: no revelamos si el email existe o no
    return {"detail": "Si el email es válido, recibirás un enlace de acceso"}


@router.post("/magic-link/verify", response_model=TokenOut)
def verify_magic_link(token: str, response: Response, db: Session = Depends(get_db)):
    row = db.scalar(
        select(AuthToken).where(
            AuthToken.token_hash == hashlib.sha256(token.encode()).hexdigest(),
            AuthToken.purpose == "magic_link",
        )
    )
    now = datetime.now(timezone.utc)
    if row is None or row.used_at is not None or as_utc(row.expires_at) < now:
        raise HTTPException(400, "Enlace inválido o caducado, pide uno nuevo")
    row.used_at = now
    user = _get_or_create_user(db, row.email, idioma=row.idioma)
    db.commit()
    return _set_session(response, db, user)


# --- Sesión ---

@router.post("/refresh", response_model=TokenOut)
def refresh_session(
    response: Response,
    db: Session = Depends(get_db),
    raw: str | None = Depends(get_refresh_cookie),
):
    if raw is None:
        raise HTTPException(401, "Sin sesión")
    result = rotate_refresh_token(db, raw)
    if result is None:
        raise HTTPException(401, "Sesión caducada, vuelve a entrar")
    user, new_raw = result
    response.set_cookie(
        REFRESH_COOKIE,
        new_raw,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=get_settings().refresh_token_days * 86400,
        path=get_settings().refresh_cookie_path,
    )
    return TokenOut(access_token=create_access_token(user))


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    raw: str | None = Depends(get_refresh_cookie),
):
    if raw:
        revoke_refresh_token(db, raw)
    response.delete_cookie(REFRESH_COOKIE, path=get_settings().refresh_cookie_path)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return user

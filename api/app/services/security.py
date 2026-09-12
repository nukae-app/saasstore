"""JWT de acceso + refresh tokens opacos (solo se guarda su hash)."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import AuthToken, RefreshToken, User

ALGORITHM = "HS256"


def as_utc(dt: datetime) -> datetime:
    """SQLite devuelve datetimes naive; Postgres, aware. Normaliza a UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
REFRESH_COOKIE = "ulr_refresh"


def get_or_create_user(db: Session, email: str, nombre: str | None = None, idioma: str | None = None) -> User:
    """Compartido entre los flujos de login web (`routers/auth.py`) y nativo
    (`routers/auth_mobile.py`) — misma resolución de usuario por email
    verificado en los dos, una sola implementación."""
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        # email_verified=True: la posesión del email ya queda probada por el propio
        # flujo (magic link canjeado o Google con email_verified=True en el id_token).
        user = User(email=email.lower(), name=nombre, email_verified=True, language=idioma or "ca")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def create_magic_link_token(db: Session, email: str, expires_delta: timedelta) -> str:
    """Genera un magic link d'un sol ús amb la caducitat indicada i el desa
    (hash) a AuthToken — el mateix mecanisme que /auth/magic-link, però amb
    caducitats més llargues per a fluxos que no són un login immediat (p.ex.
    acceptar per email el preu d'una petició, que pot trigar dies a mirar-se)."""
    raw = secrets.token_urlsafe(32)
    db.add(AuthToken(
        email=email.lower(),
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        purpose="magic_link",
        expires_at=datetime.now(timezone.utc) + expires_delta,
    ))
    db.commit()
    return raw


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user: User) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "rol": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
    }
    return jwt.encode(payload, s.secret_key, algorithm=ALGORITHM)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_refresh_token(db: Session, user: User) -> str:
    s = get_settings()
    raw = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(days=s.refresh_token_days),
        )
    )
    db.commit()
    return raw


def revoke_all_refresh_tokens(db: Session, user_id: uuid.UUID) -> None:
    """Revoca todos los refresh tokens activos de un usuario. Se usa como
    respuesta a un reuso detectado en `rotate_refresh_token` (ver abajo):
    en vez de limitarse a rechazar el token reutilizado, fuerza relogin en
    TODOS los dispositivos — la señal de que alguien más tiene una copia
    afecta a la cuenta entera, no solo a esa sesión."""
    rows = db.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    )
    now = datetime.now(timezone.utc)
    for row in rows:
        row.revoked_at = now
    db.commit()


def rotate_refresh_token(db: Session, raw: str) -> tuple[User, str] | None:
    """Valida el refresh token, lo revoca y emite uno nuevo (rotación).

    Detección de reuso: si el token presentado YA estaba revocado (no es
    una carrera legítima — token_hash es único, solo puede haberse marcado
    revocado por una rotación o revocación anteriores), es señal de que
    alguien más tiene una copia de un token viejo — típicamente un refresh
    token robado de un dispositivo. En vez de solo devolver 401, se revocan
    todos los refresh tokens activos del usuario."""
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))
    if row is None:
        return None
    if row.revoked_at is not None:
        revoke_all_refresh_tokens(db, row.user_id)
        return None
    now = datetime.now(timezone.utc)
    if as_utc(row.expires_at) < now:
        return None
    row.revoked_at = now
    user = db.get(User, row.user_id)
    if user is None:
        return None
    return user, issue_refresh_token(db, user)


def revoke_refresh_token(db: Session, raw: str) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))
    if row is not None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Falta el token de acceso")
    try:
        payload = jwt.decode(auth[7:], get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido o caducado")
    user = db.get(User, uuid.UUID(payload["sub"]))
    # `db.get()` puede devolver un hit del identity map sin pasar por el
    # filtro automático de tenant (ver app/tenancy.py::_filter_by_tenant) —
    # por eso aquí la comprobación de tenant es explícita: esto es la puerta
    # de autenticación, no nos fiamos solo del filtro implícito.
    if user is None or user.tenant_id != request.state.tenant.id:
        raise HTTPException(401, "Usuario no encontrado")
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    # Segundo interlock: aunque DEV_ADMIN_BYPASS se active por error, nunca
    # se activa si el entorno se ha declarado como producción (misma señal
    # que ya distingue el TPV de Redsys entre test/production).
    if get_settings().dev_admin_bypass and get_settings().redsys_environment != "production":
        user = db.scalar(select(User).where(User.role == "admin"))
        if user is None:
            user = User(email="dev@admin.local", role="admin", name="Dev Admin")
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    user = get_current_user(request, db)
    if user.role != "admin":
        raise HTTPException(403, "Solo administración")
    return user


def get_refresh_cookie(ulr_refresh: str | None = Cookie(default=None)) -> str | None:
    return ulr_refresh

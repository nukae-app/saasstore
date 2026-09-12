"""Auth para clientes nativos (apps móviles).

Mismo mecanismo de sesión que `auth.py` (JWT de acceso corto + refresh
token rotatorio, mismas primitivas de `services/security.py`), pero
endpoints SEPARADOS y en paralelo a los de `/auth/*` — no una rama
condicional sobre los mismos. Motivo, no cosmético: una app nativa no
tiene cookie jar de navegador, así que el refresh token tiene que viajar
en el body JSON en vez de en la cookie `httpOnly` que usa el flujo web.
Si en vez de esto se hubiera añadido un header tipo `X-Client: native`
sobre los endpoints existentes para decidir la forma de la respuesta, un
XSS en la web podría haber mandado ese mismo header en su propio
`fetch()` y sacarse por JSON el refresh token que la cookie `httpOnly`
protege de JS — exactamente el vector que `httpOnly` existe para cerrar.

Con endpoints separados eso no es explotable: `/auth/mobile/refresh`
exige el token explícito en el body, nunca lo lee de cookie — un XSS no
tiene ningún valor válido que mandar (el de la web es `httpOnly`, nunca
fue legible por JS).

`/auth/mobile/magic-link` y `/magic-link/verify` van un paso más allá:
a diferencia del flujo web (que ya sabe en qué tenant está, por dominio,
antes de que el usuario escriba nada), la app de admin solo tiene el
email — un mismo email puede ser admin en más de una tienda. En vez de
obligar al usuario a escribir el slug de su tienda de memoria antes de
poder entrar, se resuelve el tenant por el propio email/token:
- Al pedir el enlace: busca en qué tenant(s) ese email es realmente
  `admin` (nunca donde solo tiene cuenta de cliente) y manda un enlace
  por cada uno — 0, 1 o varios, el caso de varios es infrecuente pero no
  se ignora, solo significa varios emails en vez de una pantalla de
  selección.
- Al verificarlo: `AuthToken.token_hash` es único a nivel global (no por
  tenant, ver `models/users.py`), así que el propio token basta para
  encontrar de qué tenant es — el mismo patrón que ya usa
  `routers/checkout.py::redsys_notify` (`get_db_unscoped` + `scoped_to`)
  para el mismo problema (identificar el tenant antes de poder resolverlo
  por dominio/slug).

`/auth/mobile/login` (usuario/contraseña, ver CLAUDE.md punto 4 — es una
vía de entrada tan válida como el magic link, no una alternativa de
segunda) resuelve el tenant con el mismo espíritu, pero con una
ambigüedad que el magic link no tiene: un email+contraseña SÍ puede
coincidir como admin en más de un tenant a la vez (dos cuentas propias
con la misma contraseña), así que la respuesta puede pedir explícitamente
que se elija cuál (`MobileLoginOut.status == "choose_tenant"`).

Ver docs/ARQUITECTURA_APPS_NATIVAS.md §3.2 para el diseño completo.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db, get_db_unscoped
from ..models import AuthToken, Tenant, User
from ..rate_limit import limiter
from ..schemas.auth import (
    MagicLinkRequest,
    MobileLoginOut,
    MobilePasswordLoginRequest,
    MobileRefreshRequest,
    MobileTenantOption,
    MobileTokenOut,
)
from ..services.emailer import render_email_html, send_email
from ..services.security import (
    as_utc,
    create_access_token,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from ..tenancy import scoped_to

router = APIRouter(prefix="/auth/mobile", tags=["auth-mobile"])


def _send_magic_link_email_mobile(db: Session, tenant: Tenant, email: str, raw_token: str) -> None:
    """Sin Universal Link todavía (deferred, ver §3.2/§7bis del doc de
    arquitectura): el cuerpo muestra el token en claro para copiarlo a
    mano en la app. Texto fijo, no pasa por `translate()` — es un email
    interno de administración, no cara a cliente (mismo criterio que ya
    aplica el proyecto a los tiques impresos, siempre en catalán)."""
    minuts = get_settings().magic_link_minutes
    body_html = (
        f"<p>Token per entrar a l'app d'administració de <strong>{tenant.nombre}</strong> "
        f"(caduca en {minuts} minuts):</p>"
        f"<p style=\"font-family:monospace;font-size:16px;background:#f4f4f5;padding:12px;"
        f"border-radius:8px;word-break:break-all\">{raw_token}</p>"
    )
    html = render_email_html(f"Entra a {tenant.nombre}", body_html, tenant, db)
    send_email(
        email,
        f"Accés a l'app d'administració — {tenant.nombre}",
        f"Token per entrar a {tenant.nombre} (caduca en {minuts} minuts): token={raw_token}",
        tenant,
        db,
        html=html,
    )


@router.post("/magic-link", status_code=202)
@limiter.limit("10/hour")
def request_magic_link_mobile(request: Request, payload: MagicLinkRequest, db: Session = Depends(get_db_unscoped)):
    email = payload.email.lower()
    # Sin tenant resuelto todavía (get_db_unscoped) -> _filter_by_tenant no
    # filtra nada (ver tenancy.py), así que esta búsqueda ve todos los
    # tenants. Solo cuenta ser `admin` — un email con cuenta de cliente en
    # otras 10 tiendas no debe verlas aquí ni recibir nada por ellas.
    tenant_ids = db.scalars(select(User.tenant_id).where(User.email == email, User.role == "admin")).all()
    for tenant_id in tenant_ids:
        raw = secrets.token_urlsafe(32)
        with scoped_to(db, tenant_id):
            tenant = db.get(Tenant, tenant_id)
            db.add(
                AuthToken(
                    email=email,
                    token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                    purpose="magic_link",
                    idioma=payload.language,
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=get_settings().magic_link_minutes),
                )
            )
            db.commit()
            _send_magic_link_email_mobile(db, tenant, email, raw)
    # 202 siempre, mismo texto, sin importar 0/1/varios matches: si se
    # devolviera aquí la lista de tiendas, cualquiera podría usar esto para
    # averiguar de qué tiendas es admin un email ajeno. La única forma real
    # de verlo es teniendo acceso a esa bandeja de entrada.
    return {"detail": "Si el email es válido, recibirás un enlace de acceso"}


@router.post("/magic-link/verify", response_model=MobileTokenOut)
def verify_magic_link_mobile(token: str, db: Session = Depends(get_db_unscoped)):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = db.scalar(select(AuthToken).where(AuthToken.token_hash == token_hash, AuthToken.purpose == "magic_link"))
    now = datetime.now(timezone.utc)
    if row is None or row.used_at is not None or as_utc(row.expires_at) < now:
        raise HTTPException(400, "Enlace inválido o caducado, pide uno nuevo")
    with scoped_to(db, row.tenant_id):
        row.used_at = now
        # A diferencia del flujo web (`get_or_create_user`), aquí NUNCA se
        # crea un usuario nuevo: `request_magic_link_mobile` solo emitió
        # este token porque el email ya era admin de este tenant — si para
        # cuando se canjea ya no existe o dejó de ser admin, se rechaza en
        # vez de crear una cuenta nueva sin permisos.
        user = db.scalar(select(User).where(User.email == row.email))
        if user is None or user.role != "admin":
            raise HTTPException(403, "No tens accés d'administrador a aquesta botiga")
        db.commit()
        tenant = db.get(Tenant, row.tenant_id)
        return MobileTokenOut(
            access_token=create_access_token(user),
            refresh_token=issue_refresh_token(db, user),
            tenant_slug=tenant.slug,
        )


@router.post("/login", response_model=MobileLoginOut)
@limiter.limit("20/hour")
def login_mobile(request: Request, payload: MobilePasswordLoginRequest, db: Session = Depends(get_db_unscoped)):
    """Igual que `POST /auth/login` (web), pero sin tenant conocido de
    antemano — mismo problema que `/magic-link`, resuelto igual (buscar
    en qué tenant(s) es admin), con una vuelta más porque una contraseña
    SÍ puede coincidir en más de un tenant a la vez (dos cuentas propias
    con la misma contraseña) sin que eso sea nada raro, a diferencia del
    magic link (un token no puede "coincidir" en dos sitios).

    `tenant_slug` en el payload es la respuesta a esa ambigüedad: si la
    primera llamada (sin `tenant_slug`) encuentra más de un match, no
    inicia sesión en ninguno — devuelve `choose_tenant` con las opciones,
    y la app repite la llamada con el `slug` elegido."""
    email = payload.email.lower()
    if payload.tenant_slug:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == payload.tenant_slug, Tenant.activo.is_(True)))
        candidates = [db.scalar(select(User).where(User.email == email, User.tenant_id == tenant.id))] if tenant else []
    else:
        candidates = list(db.scalars(select(User).where(User.email == email, User.role == "admin")))

    matches = [
        u for u in candidates
        if u is not None and u.role == "admin" and u.active and u.email_verified and u.password_hash
        and verify_password(payload.password, u.password_hash)
    ]
    if not matches:
        raise HTTPException(401, "Email o contraseña incorrectos")

    if len(matches) > 1:
        options = [MobileTenantOption(slug=t.slug, name=t.nombre) for t in (db.get(Tenant, u.tenant_id) for u in matches)]
        return MobileLoginOut(status="choose_tenant", tenants=options)

    user = matches[0]
    with scoped_to(db, user.tenant_id):
        tenant = db.get(Tenant, user.tenant_id)
        return MobileLoginOut(
            status="signed_in",
            access_token=create_access_token(user),
            refresh_token=issue_refresh_token(db, user),
            tenant_slug=tenant.slug,
        )


@router.post("/refresh", response_model=MobileTokenOut)
def refresh_mobile(payload: MobileRefreshRequest, db: Session = Depends(get_db)):
    result = rotate_refresh_token(db, payload.refresh_token)
    if result is None:
        raise HTTPException(401, "Sesión caducada, vuelve a entrar")
    user, new_raw = result
    return MobileTokenOut(access_token=create_access_token(user), refresh_token=new_raw)


@router.post("/logout", status_code=204)
def logout_mobile(payload: MobileRefreshRequest, db: Session = Depends(get_db)):
    revoke_refresh_token(db, payload.refresh_token)

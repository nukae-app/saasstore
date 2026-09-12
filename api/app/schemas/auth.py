import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr


class MagicLinkRequest(BaseModel):
    email: EmailStr
    language: str = "ca"


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None
    language: str = "ca"


class SetPasswordRequest(BaseModel):
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MobileTokenOut(BaseModel):
    """Igual que TokenOut, pero además incluye el refresh token en el body —
    los clientes nativos (`routers/auth_mobile.py`) no tienen cookie jar de
    navegador, así que no pueden depender de la cookie httpOnly que usa el
    flujo web. Ver docs/ARQUITECTURA_APPS_NATIVAS.md §3.2.

    `tenant_slug` solo lo rellena `/auth/mobile/magic-link/verify` (ver
    §7bis-2): es la única llamada donde el cliente todavía no sabe de qué
    tenant es, así que se lo dice el servidor — `refresh`/`logout` ya
    reciben el slug del propio cliente (guardado tras el login) y no lo
    necesitan de vuelta."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    tenant_slug: str | None = None


class MobileRefreshRequest(BaseModel):
    refresh_token: str


class MobilePasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str
    # Solo hace falta en la SEGUNDA llamada, cuando la primera responde
    # "choose_tenant" (ver MobileLoginOut) porque el mismo email+contraseña
    # es válido como admin en más de un tenant — infrecuente, pero no se
    # ignora. La primera llamada nunca lo manda: no hay forma de saberlo
    # todavía.
    tenant_slug: str | None = None


class MobileTenantOption(BaseModel):
    slug: str
    name: str


class MobileLoginOut(BaseModel):
    """A diferencia del magic link (siempre resuelve a lo sumo un tenant,
    porque el token en sí ya es de uno concreto), un mismo email+contraseña
    puede ser válido como admin en más de un tenant a la vez — de ahí
    `status`: `signed_in` (caso normal, un único match, tokens rellenos) o
    `choose_tenant` (ambiguo, `tenants` rellena con las opciones — repetir
    la llamada con uno de esos `slug` en `tenant_slug`)."""

    status: Literal["signed_in", "choose_tenant"]
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    tenant_slug: str | None = None
    tenants: list[MobileTenantOption] | None = None


class MeOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str | None
    role: str
    language: str

    model_config = {"from_attributes": True}


# --- Carrito y checkout ---

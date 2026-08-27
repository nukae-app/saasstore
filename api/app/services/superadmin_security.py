"""Autenticación del superadmin de plataforma (Fase 2) — realm completamente
separado del de cada tienda (ver services/security.py::create_access_token/
get_current_user): clave de firma propia (SuperAdminSettings.superadmin_secret_key,
NUNCA Settings.secret_key), claims propios, sin ninguna comprobación de
tenant — este realm no pertenece a ninguno, ve y gestiona todos."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import get_superadmin_settings
from ..database import get_db_unscoped
from ..models import PlatformAdmin, PlatformAdminAuditLog, PlatformAdminRole

ALGORITHM = "HS256"
ACCESS_TOKEN_HOURS = 8


def create_superadmin_token(admin: PlatformAdmin) -> str:
    s = get_superadmin_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(admin.id),
        "iat": now,
        "exp": now + timedelta(hours=ACCESS_TOKEN_HOURS),
    }
    return jwt.encode(payload, s.superadmin_secret_key, algorithm=ALGORITHM)


def get_current_superadmin(request: Request, db: Session = Depends(get_db_unscoped)) -> PlatformAdmin:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Falta el token de acceso")
    try:
        payload = jwt.decode(
            auth[7:], get_superadmin_settings().superadmin_secret_key, algorithms=[ALGORITHM]
        )
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido o caducado")
    # PlatformAdmin no hereda de TenantScoped: db.get() aquí nunca se ve
    # afectado por el filtro de tenant (ver app/tenancy.py), esté puesto o no.
    admin = db.get(PlatformAdmin, uuid.UUID(payload["sub"]))
    if admin is None or not admin.activo:
        raise HTTPException(401, "Administrador no encontrado")
    return admin


# Alias para el estilo de dependencia de router ya usado con `require_admin`
# (ver services/security.py) — para endpoints de solo lectura, pertenecer a
# `platform_admins` ya basta, sin importar el rol.
require_superadmin = get_current_superadmin


def require_superadmin_role(*roles: PlatformAdminRole):
    """Factory de dependencia (mismo estilo que require_admin) para
    endpoints mutables: además de estar autenticado, el rol debe estar en
    `roles`. Uso: `Depends(require_superadmin_role(PlatformAdminRole.owner))`."""

    def _dependency(admin: PlatformAdmin = Depends(get_current_superadmin)) -> PlatformAdmin:
        if admin.role not in roles:
            raise HTTPException(403, "Tu rol no tiene permiso para esta acción")
        return admin

    return _dependency


def record_audit(
    db: Session, admin: PlatformAdmin, action: str,
    target_tenant_id: uuid.UUID | None = None, details: dict | None = None,
) -> None:
    """Escribe una fila de auditoría. Se llama DESPUÉS de que la mutación en
    sí haya hecho commit (mismo momento en que superadmin.py ya hacía sus
    propios commits) — un fallo al auditar no debe deshacer una acción que
    ya tuvo éxito, así que esto hace su propio commit por separado."""
    db.add(PlatformAdminAuditLog(
        platform_admin_id=admin.id, action=action,
        target_tenant_id=target_tenant_id, details=details,
    ))
    db.commit()

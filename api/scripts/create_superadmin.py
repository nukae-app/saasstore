"""Arranque en frío del panel de superadmin (Fase 2): crea el primer
`PlatformAdmin`. No puede haber un primer superadmin creado a través de un
endpoint que ya requiere ser superadmin — se ejecuta una vez, a mano.

Uso:
  docker compose exec api python -m scripts.create_superadmin --email tu@email.com
  (pide la contraseña de forma interactiva, sin dejarla en el historial de la shell)
"""

import argparse
import getpass

from sqlalchemy import select

from app.database import SessionLocal
from app.models import PlatformAdmin, PlatformAdminRole
from app.services.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--nombre")
    parser.add_argument(
        "--role", choices=[r.value for r in PlatformAdminRole], default=PlatformAdminRole.owner.value,
        help="owner (control total) o support (solo lectura). Por defecto: owner.",
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    password = getpass.getpass("Contraseña: ")
    password_confirm = getpass.getpass("Repite la contraseña: ")
    if password != password_confirm:
        raise SystemExit("Las contraseñas no coinciden.")
    if len(password) < 8:
        raise SystemExit("La contraseña debe tener mínimo 8 caracteres.")

    db = SessionLocal()
    try:
        if db.scalar(select(PlatformAdmin).where(PlatformAdmin.email == email)):
            raise SystemExit(f"Ya existe un PlatformAdmin con email '{email}'.")
        admin = PlatformAdmin(
            email=email, password_hash=hash_password(password), nombre=args.nombre,
            role=PlatformAdminRole(args.role),
        )
        db.add(admin)
        db.commit()
        print(f"PlatformAdmin creado: {email} (role={admin.role.value})")
    finally:
        db.close()


if __name__ == "__main__":
    main()

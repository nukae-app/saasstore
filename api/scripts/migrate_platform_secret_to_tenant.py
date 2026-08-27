"""Runbook puntual de la Fase 2 (secretos por tenant, ver app/tenant_secrets.py):
copia las credenciales de Redsys/Discogs/Spotify que hasta ahora vivían en el
secreto de plataforma (`AWS_SECRETS_NAME`, ver app/config.py) al secreto
propio del tenant `recordstore` (o el que se indique) en Secrets Manager.

Ejecutar UNA VEZ, antes de desplegar esta fase en un entorno con datos reales
— después de esto, el secreto de plataforma deja de ser la fuente de verdad
para estos campos (aunque `redsys_*` se ha dejado en Settings porque un par
de rutas ya deferidas — services/redsys.py::charge_recurring, el webhook de
alta de suscripción — todavía lo leen así, ver notas en esos ficheros).

Uso:
  docker compose exec api python -m scripts.migrate_platform_secret_to_tenant \\
      --tenant recordstore \\
      --redsys-merchant-code 123456789 --redsys-terminal 1 --redsys-secret-key "..." \\
      --discogs-token "..." --spotify-client-id "..." --spotify-client-secret "..."

Los valores que no se pasen se dejan tal cual estén ya en el secreto del
tenant (no se sobreescriben con vacío).
"""

import argparse

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Tenant
from app.tenant_secrets import provision_tenant_secret, set_tenant_secret


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant", required=True, help="Slug del tenant (ver tabla tenants)")
    parser.add_argument("--redsys-merchant-code")
    parser.add_argument("--redsys-terminal")
    parser.add_argument("--redsys-secret-key")
    parser.add_argument("--discogs-token")
    parser.add_argument("--spotify-client-id")
    parser.add_argument("--spotify-client-secret")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == args.tenant))
        if tenant is None:
            raise SystemExit(f"No existe ningún tenant con slug '{args.tenant}'")

        provision_tenant_secret(tenant.id)
        fields = {
            "redsys_merchant_code": args.redsys_merchant_code,
            "redsys_terminal": args.redsys_terminal,
            "redsys_secret_key": args.redsys_secret_key,
            "discogs_token": args.discogs_token,
            "spotify_client_id": args.spotify_client_id,
            "spotify_client_secret": args.spotify_client_secret,
        }
        fields = {k: v for k, v in fields.items() if v is not None}
        if not fields:
            raise SystemExit("No se ha pasado ningún valor a migrar.")
        set_tenant_secret(tenant.id, **fields)
        print(f"Migrados a saaswebstore/tenants/{tenant.id} ({tenant.slug}): {sorted(fields)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""Pull de comandes del Marketplace de Discogs cap a la taula `orders` (origen='discogs').

Pensat per cron al VPS, p. ex. cada 20 minuts (un tenant per línia de cron):
    */20 * * * * cd /home/ubuntu/recordshop && docker compose exec -T api python -m scripts.sync_discogs_orders --tenant recordstore >> /var/log/discogs_orders_sync.log 2>&1

També es pot disparar a demanda des de l'admin (POST /admin/discogs/sync/orders).

Fase 2 (secretos por tenant, ver app/tenant_secrets.py): este script abre su
propia sesión sin tenant — `Item`/`Order` son TenantScoped, así que hace
falta `--tenant` explícito y envolver el trabajo en `scoped_to`, o cualquier
INSERT revienta con IntegrityError (tenant_id NOT NULL sin valor)."""

import argparse

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Tenant
from app.services.discogs_sync import sync_discogs_orders
from app.tenancy import scoped_to
from app.tenant_secrets import get_tenant_secrets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True, help="Slug del tenant (ver tabla tenants)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == args.tenant))
        if tenant is None:
            raise SystemExit(f"No existe ningún tenant con slug '{args.tenant}'")
        with scoped_to(db, tenant.id):
            token = get_tenant_secrets(tenant.id).discogs_token
            resum = sync_discogs_orders(db, token)
        print(f"Discogs orders sync ({tenant.slug}): {resum}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
